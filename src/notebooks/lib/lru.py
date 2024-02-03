from collections import deque
from typing import Any

from lib.utilities import setup_logging, load_yaml

logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('LRU')
LOG.setLevel(logging.DEBUG)

CONFIGS = load_yaml('configs/config.yaml')['LRU']


class LRU:
    def __init__(self, configs: dict = CONFIGS):
        self.__dict__.update(configs)
        self._create_empty_deck(maxlen=configs['maxlen'])

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name == 'count':
            self.__dict__[__name] = __value

            # Check if deck is full, if so, set the deck_full flag.
            if __value >= self.maxlen:
                self.deck_full = True
                    
            elif __value < self.maxlen:
                self.deck_full = False

        else:
            self.__dict__[__name] = __value

    def __contains__(self, key: str) -> bool:
        return key in self.cache
    
    def __len__(self) -> int:
        return len(self.cache)
    
    def __delitem__(self, key: str):
        if key in self.cache:
            self.cache.pop(key)
            self.deck.remove(key)
            self.count -= 1

    def __iter__(self) -> str:
        '''Iterate through the keys in the deck, 
        starting with the most recent key retrieved.'''
        deck = self.deck.copy()
        deck.reverse()
        
        for k in deck:
            yield k

    def __getitem__(self, key: str) -> Any:
        try:
            value = self.cache[key]
            # Reorder the deck
            self.deck.remove(key)
            self.deck.append(key)
        except KeyError:
            raise
        except ValueError as error:
            # Exception occurs when key is not in the deck
            LOG.exception(f'__getitem__, deck={self.deck}')
            raise
        else:
            return value

    def __setitem__(self, key: str, value: Any) -> None:   
        try:
            # Update the cache
            self.cache[key] = value

            # Reorder the deck
            self.deck.remove(key)
            self.deck.append(key)
        except ValueError:
            # Exception occurs when key is not in the deck
            self.deck.append(key)
            self.count += 1

    def _create_empty_deck(self, maxlen: None | int = None) -> None:
        if maxlen is not None:
            self.maxlen = maxlen

        self.deck = deque(maxlen=self.maxlen)
        self.cache = {}
        self.count = 0

        LOG.info(f'cache initialized with deque of max size={self.maxlen}.')

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.cache:
            return self[key]
        return default
    
    def _split_deck(self) -> list:
        '''Split the deck into two lists, the oldest and the newest keys.
        The oldest keys will be returned, 
        and the newest keys will be kept in the deck.'''
        split = int(self.maxlen * self.sync_fraction)
        
        # New keys to be kept in the deck
        old_keys = list(self.deck)[:split]
        new_keys = list(self.deck)[split:]
        self.deck = deque(new_keys, maxlen=self.maxlen)

        # Old keys to be synced
        return old_keys
               
    def sync_make_ready(self) -> dict:
        '''Remove the old keys from the deck and recreate the deck with the newest keys.
        This should be followed by a call to update the database with the sync_store.'''
        sync_store = {}

        # Split the deck and move the old keys to the sync_store
        for key in self._split_deck():
            sync_store[key] = self.cache.pop(key)
            self.count -= 1

        LOG.info(f'sync_store created with "{len(sync_store)}" keys.')

        return sync_store

def test():
    configs = load_yaml('configs/config.yaml')['LRU']

    try:
        # Init and fill LRU
        lru_size = 4
        lru = LRU()
        lru.maxlen = lru_size

        # [0, 1, 2]
        for i in range(lru_size-1):
            lru[f'{i}'] = i

        # contains
        assert '0' in lru, 'LRU: contains in fail'
        assert '9' not in lru, 'LRU: contains in fail'

        # get. [1, 2, 0]
        x = lru['0']
        assert x == 0, 'LRU: get fail'
        assert lru.deck[-1] == '0', 'LRU: __getitem__ failed to rotate key to most recent position in LRU'
        
        x = lru.get('9', 'pass')
        assert x == 'pass', 'LRU: get() fail'
        
        # iter - most recent first
        y = [x for x in lru]
        assert y == ['0', '2', '1'], f'LRU: iter fail, {y}'

        # Full? [1, 2, 0, 3] -> [0, 3] after sync
        lru['3'] = 3
        assert lru.deck_full, 'LRU: Failed to identify LRU as full'

        # Sync
        sync_store = lru.sync_make_ready()
        assert '1' in sync_store, f'LRU: sync store fail, 1 not in {sync_store}'
        assert '2' in sync_store, f'LRU: sync store fail, 2 not in {sync_store}'
        assert '0' not in sync_store, f'LRU: sync store fail, 0 in {sync_store}'
        assert '3' not in sync_store, f'LRU: sync store fail, 3 in {sync_store}'
    except Exception as error:
        LOG.exception(f'LRU Test Failed: {error}', exc_info=True)
        raise
    else:
        LOG.info('LRU Test completed successfully.')
        return True
    

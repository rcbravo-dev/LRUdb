from lib.utilities import setup_logging
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('LRU')
LOG.setLevel(logging.DEBUG)

from collections import deque


class LRU:
    def __init__(self, maxlen=100):
        self.maxlen = maxlen
        self.deck = deque(maxlen=self.maxlen)
        self.cache = {}
        self.count = 0
        self.deck_full = False

    def __contains__(self, key):
        return key in self.cache

    def __delitem__(self, key):
        if key in self.cache:
            self.deck.remove(key)
            self.cache.pop(key)
            
            # The deck is no longer full
            self.deck_full = False
            self.count -= 1

    def __iter__(self):
        for k in self.cache.keys():
            yield k

    def __len__(self):
        return len(self.cache)
    
    def __getitem__(self, key):
        try:
            value = self.cache[key]
        except KeyError:
            raise
        else:
            self.deck.remove(key)
            self.deck.append(key)
            return value
    
    def __setitem__(self, key, value):     
        if key in self.cache:
            # Reorder the deck
            self.deck.remove(key)
            self.deck.append(key)
            # Update the cache
            self.cache[key] = value
        else:
            # New key placed in cache
            self.cache[key] = value
            self.deck.append(key)
            self.count += 1
            if self.count == self.maxlen:
                self.deck_full = True
            
    def get(self, key, default=None):
        if key in self.cache:
            return self[key]
        return default
               
    def sync_make_ready(self, fraction_of_cache=0.5):
        # Remove the old keys from the deck and recreate the deck with the newest keys
        split = int(self.maxlen * fraction_of_cache)
        
        self.sync_store = list(self.deck)[:split]
        
        new_keys = list(self.deck)[split:]
        self.deck = deque(new_keys, maxlen=self.maxlen)


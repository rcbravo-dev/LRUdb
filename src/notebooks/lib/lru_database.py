from collections import namedtuple
from io import BytesIO
from pickle import DEFAULT_PROTOCOL, Pickler, Unpickler
from typing import Any

from lib.utilities import setup_logging, load_yaml
from lib.database import AsyncDataBase
from lib.database import test as AsyncDataBase_test
from lib.lru import LRU
from lib.lru import test as LRU_test

logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('LRU_db')
LOG.setLevel(logging.DEBUG)

CONFIGS = load_yaml('configs/config.yaml')['LRU_db']
CONFIGS['protocol'] = DEFAULT_PROTOCOL

Node = namedtuple('Node', ['node_id', 'node'])


class LRUDataBase:
    def __init__(self, file_name: str, table_name: str, configs: dict = CONFIGS) -> None:
        self.file_name = file_name
        self.table_name = table_name
        self.__dict__.update(configs)
    
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, type, value, traceback):
        await self.close()
    
    def __aiter__(self):
        '''Called by: async for x in self:'''
        return self

    async def __anext__(self):
        '''Called by: async for x in self:'''
        try:
            if not hasattr(self, '_database_keys'):
                # Get the keys from the database, returns a list of keys: str
                self._database_keys = await self.node_keys()
                
                # Add the LRU keys to the database keys. The LRU
                # can be updated without writing to the database.
                # The deck is a deque of bytes.
                for k in list(self.lru.deck):
                    key = self._decode_key(k)
                    if key in self._database_keys:
                        pass
                    else:
                        self._database_keys.append(key)

            # Removes the last key from the list, this will 
            # generally be the most recently used key.
            _next = self._database_keys.pop()
        except IndexError:
            self.__dict__.pop('_database_keys')
            raise StopAsyncIteration
        else:
            return _next

    async def connect(self, database_path: str | None = None) -> None:
        self.lru = LRU()
    
        # Creates the connection thread and the cursor
        # Create(if not already made) a table named 'table_name'
        if database_path is not None:
            self.db = AsyncDataBase(self.file_name, self.table_name, database_path=database_path)
        else:
            self.db = AsyncDataBase(self.file_name, self.table_name)

        await self.db.open_connection()
        await self.db.create()
                
    async def write(self, key: str, value: Any) -> None:
        '''This method first writes to the LRU cache. If the cache is full it prepares 
        the oldest data in the LRU for offloading to the database, then writes to the 
        database by calling sync().'''
        self.lru[self._encode_key(key)] = self._serialize(value)

        if self.lru.deck_full:
            await self.sync()
        
    async def read(self, key: str | list) -> Any | list:
        if isinstance(key, str):
            try:
                key = self._encode_key(key)

                # Check if key is in the LRU
                value = self.lru[key]
            except KeyError:
                # Key is not in the LRU, check the database. blob is a Node object
                blob = await self.db.read(key)

                if blob:
                    # Add the key and serialized value to the LRU
                    await self.write(key, blob.node)

                    # Un_serialize the value and return
                    return self._un_serialize(blob.node)
                else:
                    # No blob was returned, key is not in the database or LRU
                    return None
            else:
                # Key is in the LRU, return the value
                return self._un_serialize(value)
            
        elif isinstance(key, list):
            return await self._read_many(key)
        
    async def get(self, key: str, default: Any = None) -> Any:
        '''Returns the unserialized value of the key. If not in the 
        database or LRU, returns default.'''
        results = await self.read(key)
        if results is None:
            return default
        return results

    async def _read_many(self, keys: list) -> dict:
        read_from_db = []
        results = {}

        # First check the LRU for the keys
        for key in keys:
            try:
                _key = self._encode_key(key)

                value = self.lru[_key]
            except KeyError:
                # If key not in the LRU, add to the read list
                results[key] = None
                read_from_db.append(_key)
                continue
            else:
                # If key is in the LRU, add to the results dict
                results[key] = self._un_serialize(value)
        
        # If all keys are in the LRU, return the results, 
        # else read from the database to get the missing keys
        if read_from_db:
            # Send the list to the database and get a list of Node objects
            blob_list = await self.db.read(read_from_db)
            
            for blob in blob_list:
                # Update the LRU
                await self.write(blob.node_id, blob.node)

                # Get the next node in the blob and un_serialize
                key = self._decode_key(blob.node_id)
                value = self._un_serialize(blob.node)
                
                # Update the results dict
                results[key] = value

        return results

    async def node_keys(self) -> list:
        '''Retrieves all the keys from the database'''
        keys = await self.db.node_keys()
        return [self._decode_key(key) for key in keys]
    
    async def delete(self, key: str) -> None:
        '''del self[key]'''
        key = self._encode_key(key)

        await self.db.delete_node(key)
        
        try:
            del self.lru[key]
        except KeyError:
            pass

    async def flush_cache(self):
        try:
            # Flush the LRU cache to the database
            await self.db.write(self.lru.cache)    
            cache_size = len(self.lru)
        except Exception as error:
            LOG.exception(f'flush_cache: {error}')
            raise
        else:
            self.lru._create_empty_deck()
            LOG.info(f'Flushed the LRU cache, shelve_name={self.table_name}, count={cache_size}')
            
    async def sync(self):
        try:
            sync_store = self.lru.sync_make_ready()

            # Write the sync_store (old items in LRU cahce) to the database
            await self.db.write(sync_store)

            if len(self.lru.cache) != self.lru.count:
                raise ValueError(f'Sync did not off load all LRU cache items. len_lru={len(self.lru.cache)} != cnt_lru={self.lru.count}')
        except Exception as error:
            LOG.exception(f'sync: {error}')
            raise
        else:
            LOG.info(f'Sync offloaded old cached items to the database, shelve_name={self.table_name}, count={len(sync_store)}')
   
    async def close(self):
        try:
            await self.flush_cache()
            await self.db.close()
        except Exception as error:
            LOG.exception(f'close: {error}')
            raise     
        else:
            self.lru = None
            self.db = None
            LOG.info(f'Closed LRUDataBase table: {self.table_name}')       

    def _encode_key(self, key: str) -> bytes:
        if isinstance(key, bytes):
            return key
        else:
            return key.encode(self.keyencoding)
    
    def _decode_key(self, key: bytes) -> str:
        if isinstance(key, str):
            return key
        else:
            return key.decode(self.keyencoding)
    
    def _serialize(self, value) -> bytes:
        if isinstance(value, bytes):
            return value
        else:
            f = BytesIO()
            p = Pickler(f, self.protocol)
            p.dump(value)        
            return f.getvalue()
    
    def _un_serialize(self, blob: bytes) -> Any:
        if not isinstance(blob, bytes):
            return blob
        else:
            f = BytesIO(blob)
            return Unpickler(f).load()      
        
    
async def test(db_size:int = 10, verbose: bool = False) -> bool:
    import hashlib
    from pathlib import Path
    from pickle import DEFAULT_PROTOCOL
    from lib.utilities import CWD
    configs = load_yaml('configs/config.yaml')['LRU_db']
    configs['protocol'] = DEFAULT_PROTOCOL

    test_database = CWD + 'database/zkp_test_db.db'

    try:
        # Test data
        data = {}
        for i in range(db_size * 2):
            key = f'key{i}'
            value = hashlib.sha256(str(key).encode('utf-8')).hexdigest()
            data[key] = value[:10]
        if verbose:
            print('data: ', data)
        
        # Test the AsyncDataBase
        assert await AsyncDataBase_test(), 'Database test failed'

        # Test the LRU
        assert LRU_test(), 'LRU test failed'
        
        # Test the LRUDataBase
        shelf = LRUDataBase('test_database', 'test_case', configs=configs)
        await shelf.connect()
        shelf.lru.maxlen = db_size
        if verbose:
            print('shelf connected, size=', shelf.lru.maxlen)

        # Tests writes: This will fill the LRU but will not sync to the database.
        cnt = 0
        for k, v in data.items():
            await shelf.write(k, v)
            if verbose:
                print('Added to shelf: ', k, v)
            cnt += 1
            if cnt == (db_size - 1):
                break

        # Add to shelf last key should be key9
        assert k == f'key{cnt - 1}', f'key{cnt - 1} not last key: {k}'
        
        # Test writes to unfull LRU
        lru_keys = shelf.lru.deck
        db_keys = await shelf.node_keys()

        # LRU should be full so key0 should be in the LRU
        assert b'key0' in lru_keys, f'shelf synced too early: {lru_keys}'

        # Database keys should be empty. The LRU is not full, and therefor 
        # has not requested a database sync.
        assert len(db_keys) == 0, f'shelf synced too early: {db_keys}'
        
        # Write to force database/LRU sync. Once database is full a sync is
        # ordered.
        await shelf.write('key9', data['key9'])
        lru_keys = shelf.lru.deck
        # list of strings
        db_keys = await shelf.node_keys()

        if verbose:
            print('lru: ', lru_keys)
            print('db: ', db_keys)
            print('deck full?', shelf.lru.deck_full)

        # Key0 was should have been offloaded to the database and should not be in the LRU
        assert b'key0' not in lru_keys, f'shelf synced fail: {lru_keys}'

        # Key0 should be in the database
        assert 'key0' in db_keys, f'shelf synced too early: {db_keys}'

        # Test __aiter__
        async for item in shelf:
            if verbose:
                print('aiter for loop: ', item)
            else:
                pass
        assert item == 'key0', f'__aiter__ failed: {item}'

        # Tests reads
        if verbose:
            print('lru: ', shelf.lru.deck)
            print('cache: ', shelf.lru.cache) 

        # Test delete and list comprehension
        await shelf.delete('key0')
        node_list = [x async for x in shelf]
        assert 'key0' not in node_list, f'key0 not deleted from DB and LRU: {node_list}'

        # Test read moves the key to the most recently used position in the LRU
        await shelf.read('key1')
        assert b'key1' in shelf.lru.deck, f'key1 not in LRU: {shelf.lru.deck}'
        assert shelf.lru.deck[-1] == b'key1', f'key1 was not moved to the end of the LRU: {shelf.lru.deck}'
    
        # Test read_many
        keys = ['key1', 'key2', 'key3', 'key0']
        results = await shelf.read(keys)
        for k in keys[:3]:
            assert k in results, f'{k} not in results: {results}'
            assert results[k] == data[k], f'{k} value "{results[k]}" incorrect, should be {data[k]}'
        assert results['key0'] is None, f'key0 should be None: {results["key0"]}'
        
        # Key0 should not be in the LRU because it was deleted above
        assert b'key0' not in shelf.lru.deck, f'key0 should not be in LRU: {shelf.lru.deck}'
        if verbose:
            print('lru: ', shelf.lru.deck)

        # Test get
        get = await shelf.get('key0', 'NO KEY')
        assert get == 'NO KEY', f'get failed: {get}'

    except Exception as err:
        LOG.error(f'LRUDataBase Test Failed: {err}')
        raise
    else:
        LOG.info('LRUDataBase Test Completed Successfully')
        return True
    finally:
        database_path = Path(shelf.db.database_path)
        await shelf.close()
        database_path.unlink()
        if verbose:
            print('db closed')
        
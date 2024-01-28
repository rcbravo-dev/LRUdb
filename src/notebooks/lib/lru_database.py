from lib.utilities import setup_logging
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('Shelf')
LOG.setLevel(logging.DEBUG)

import asyncio
from pickle import DEFAULT_PROTOCOL, Pickler, Unpickler
from io import BytesIO
from collections import namedtuple

from lib.database import AsyncDataBase
from lib.database import test as AsyncDataBase_test
from lib.lru import LRU

Node = namedtuple('Node', ['node_id', 'node'])


class LRUDataBase:

    """Base class for shelf implementations.
    This is initialized with a dictionary-like object.
    See the module's __doc__ string for an overview of the interface.
    """

    def __init__(self, name, cache_size: int = 500, keyencoding: str = 'utf-8', protocol: int = DEFAULT_PROTOCOL) -> None:
        self.name = name
        self.cache_size = cache_size
        self.keyencoding = keyencoding
        self.protocol = protocol  
    
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
        if not hasattr(self, '_database_keys'):
            self._database_keys = await self.node_keys()
            
            for key in list(self.lru.deck):
                if key in self._database_keys:
                    pass
                else:
                    self._database_keys.append(key)

        if len(self._database_keys) > 0:
            return self._database_keys.pop(0)
        else:
            self.__dict__.pop('_database_keys')
            raise StopAsyncIteration

    async def connect(self):
        self.lru = LRU(maxlen=self.cache_size)
        self.db = AsyncDataBase(self.name)
        
        # Creates the connection thread and the cursor
        await self.db.open_connection()
        
        # Create(if not already made) a table named 'name' with filename location/name.db
        await self.db.create()
        
    async def write(self, key, value) -> None:
        '''This method first checks that the LRU is not full, if it is, it prepares the oldest data
        in the LRU for offloading to the database, then writes to the database by calling 
        sync(). Finally, it adds the new data to the LRU.'''
        if self.lru.deck_full:
            await self.sync()
        
        self.lru[key] = value

    async def read(self, key: str | list):
        if isinstance(key, str):
            try:
                # Check if key is in the LRU
                value = self.lru[key]
            except KeyError:
                # Key is not in the LRU, check the database
                # blob = self.loop(self.db.check_out(key.encode(self.keyencoding)))
                blob = await self.db.read(key.encode(self.keyencoding))

                if blob:
                    # If a blob was returned, 
                    value = self._un_serialize(blob.node)

                    # Add the key to the LRU
                    await self.write(key, value)
                    return value
                else:
                    # No blob was returned, key is not in the database or LRU
                    return None
            else:
                # Key is in the LRU, return the value
                return value
            
        elif isinstance(key, list):
            return await self._read_many(key)
        
    async def get(self, key: str, default=None):
        '''Returns namedtuple with type(node) == bytes'''
        results = await self.read(key)
        if results is None:
            return default
        
        return results

    async def _read_many(self, keys: list):
        read_from_db = []
        results = {}
        # First check the LRU for the keys
        for i, key in enumerate(keys):
            try:
                value = self.lru[key]
            except KeyError:
                # If key not in the LRU, add to the get list
                results[key] = None
                read_from_db.append(key.encode(self.keyencoding))
                continue
            else:
                # If key is in the LRU, add to the results dict
                results[key] = value
        
        # Send the list to the database and get a list of Node objects
        blob_list = await self.db.read(read_from_db)
        
        for blob in blob_list:
            # Get the next node in the blob and un_serialize
            key = blob.node_id.decode(self.keyencoding)
            value = self._un_serialize(blob.node)
            
            # Update the results dict
            results[key] = value

            # Update the LRU
            await self.write(key, value)
        
        return results

    async def node_keys(self) -> list:
        '''Retrieves all the keys from the database'''
        keys = await self.db.node_keys()
        return [key.decode(self.keyencoding) for key in keys if type(key) == bytes]
    
    async def delete(self, key):
        '''del self[key]'''
        await self.db.delete_node(key.encode(self.keyencoding))
        
        try:
            del self.lru[key]
            
        except KeyError:
            pass

    async def flush_cache(self):
        try:
            # Flush the LRU cache to the database
            flush_store = {}
            for key in list(self.lru.deck):
                value = self.lru.cache.pop(key)
                flush_store[key.encode(self.keyencoding)] = self._serialize(value)
                self.lru.count -= 1

            # Write the flush_store (lru cache) to the database
            await self.db.write(flush_store)

            if len(self.lru.cache) != 0:
                raise ValueError(f'Length of the LRU Cache should be 0: len={len(self.lru.cache)} != 0')     
        except ValueError as error:
            LOG.exception(f'Flush Cache error: {error}')
            raise
        else:
            LOG.info(f'Flushed the LRU cache, shelve_name={self.name}, count={len(flush_store)}')
            self.lru.deck_full = False
            
    async def sync(self, fraction_of_cache=0.5):
        try:
            self.lru.sync_make_ready()

            sync_store = {}
            for key in self.lru.sync_store:
                value = self.lru.cache.pop(key)
                sync_store[key.encode(self.keyencoding)] = self._serialize(value)
                self.lru.count -= 1

            # Write the sync_store (old items in LRU cahce) to the database
            await self.db.write(sync_store)

            if len(self.lru.cache) != self.lru.count:
                raise ValueError(f'Sync did not off load all LRU cache items. len_lru={len(self.lru.cache)} != cnt_lru={self.lru.count}')
        except ValueError as error:
            LOG.exception(f'Sync error: {error}')
            raise
        else:
            LOG.info(f'Sync offloaded cached items to the database, shelve_name={self.name}, count={len(sync_store)}')
            self.lru.deck_full = False
   
    async def close(self):
        try:
            await self.flush_cache()
            del self.lru
        except Exception as error:
            LOG.exception(f'Close error: {error}')
            raise
        finally:
            await self.db.close()

    def _serialize(self, value):
        f = BytesIO()
        p = Pickler(f, self.protocol)
        p.dump(value)        
        return f.getvalue()
    
    def _un_serialize(self, blob: bytes):
        f = BytesIO(blob)
        return Unpickler(f).load()      
        
    
async def test(db_size:int = 10, verbose: bool = False) -> bool:
    import hashlib

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

        # Test the LRUDataBase
        shelf = LRUDataBase('test_database', cache_size=db_size)
        await shelf.connect()

        # Tests writes: This will fill the LRU but will not sync to the database.
        cnt = 0
        for k, v in data.items():
            await shelf.write(k, v)
            if verbose:
                print('Added to shelf: ', k, v)
            cnt += 1
            if cnt == db_size:
                break

        # Add to shelf last key should be key9
        assert k == f'key{cnt - 1}', f'key{cnt - 1} not last key: {k}'
        
        # Test writes to unfull LRU
        lru_keys = shelf.lru.deck
        db_keys = await shelf.node_keys()

        # LRU should be full so key0 should be in the LRU
        assert 'key0' in lru_keys, f'shelf synced too early: {lru_keys}'

        # Database keys should be empty
        assert len(db_keys) == 0, f'shelf synced too early: {db_keys}'
        
        # Write to force database/LRU sync
        await shelf.write('key10', data['key10'])
        lru_keys = shelf.lru.deck
        db_keys = await shelf.node_keys()

        # Key0 was should have been offloaded to the database and should not be in the LRU
        assert 'key0' not in lru_keys, f'shelf synced fail: {lru_keys}'

        # Key0 should be in the database
        assert 'key0' in db_keys, f'shelf synced too early: {db_keys}'

        # Test __aiter__
        async for item in shelf:
            if verbose:
                print('aiter for loop: ', item)
            else:
                pass
        assert item == f'key{cnt}', f'__aiter__ failed: {item}'

        # Tests reads
        if verbose:
            print('lru: ', shelf.lru.deck)
            print('cache: ', shelf.lru.cache) 

        # Test delete and list comprehension
        await shelf.delete('key0')
        del_list = [x async for x in shelf]
        assert 'key0' not in del_list, f'key0 not deleted from DB and LRU: {del_list}'

        # Test read moves the key to the most recently used position in the LRU
        await shelf.read('key1')
        assert 'key1' in shelf.lru.deck, f'key1 not in LRU: {shelf.lru.deck}'
        assert shelf.lru.deck[-1] == 'key1', f'key1 was not moved to the end of the LRU: {shelf.lru.deck}'
    
        # Test read_many
        keys = ['key1', 'key2', 'key3', 'key0']
        results = await shelf.read(keys)
        for k in keys[:3]:
            assert k in results, f'{k} not in results: {results}'
            assert results[k] == data[k], f'{k} value "{results[k]}" incorrect, should be {data[k]}'
        assert results['key0'] is None, f'key0 should be None: {results["key0"]}'
        
        # Key0 should not be in the LRU because it was deleted above
        assert 'key0' not in shelf.lru.deck, f'key0 should not be in LRU: {shelf.lru.deck}'
        if verbose:
            print('lru: ', shelf.lru.deck)

    except Exception as err:
        LOG.error(f'LRUDataBase Test Failed: {err}')
        raise
    else:
        LOG.info('LRUDataBase Test Completed Successfully')
        return True
    finally:
        await shelf.close()
        shelf.db.database_path.unlink()
        if verbose:
            print('db closed')
        
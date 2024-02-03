import aiosqlite
from collections import namedtuple
from pathlib import Path

from lib.utilities import setup_logging, CWD
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('DataBase')
LOG.setLevel(logging.DEBUG)

Node = namedtuple('Node', ['node_id', 'node'])


class AsyncDataBase:
    sqliteConnection: aiosqlite.Connection

    def __init__(self, file_name: str, table_name: str, database_path: str = CWD + 'database/'):
        self.file_name = file_name
        self.table_name = table_name
        self.database_path = Path(f'{database_path}{file_name}.db')
        self.Node = Node

    # log should be to the filename of the database
    async def open_connection(self) -> None:
        try:
            self.sqliteConnection = await aiosqlite.connect(self.database_path)
            self.sqliteConnection.row_factory = aiosqlite.Row
            self.cursor = await self.sqliteConnection.cursor()
        except aiosqlite.Error as error:
            LOG.exception(f'open_connection: {error}')
            raise
        except Exception as error:
            LOG.exception(f'open_connection: {error}')
            raise
        else:
            LOG.info(f'Connection to "{self.table_name}" established.')
    
    async def create(self) -> None:
        try:
            await self.cursor.execute(
                f'''CREATE TABLE IF NOT EXISTS {self.table_name} (
                "node_id" text PRIMARY KEY,
                "node" blob)''')
            await self.sqliteConnection.commit()
        except aiosqlite.Error as error:
            LOG.exception(f'create: {error}')
            raise
        except Exception as error:
            LOG.exception(f'create: {error}')
            raise
        else:
            LOG.info(f'Table "{self.table_name}" successfully created.')
            return None

    async def write(self, values: tuple | dict) -> None:
        '''This method inputs "values" only because it is only used when the
        LRU cache is being synced with the main database. The values are
        a list or tuple when inserting single key:value pairs, and a dict when
        inserting multiple key:value pairs. '''
        try:
            if isinstance(values, (tuple, list)):
                await self.cursor.execute(
                    f"INSERT OR REPLACE INTO {self.table_name} VALUES(?, ?)", 
                    list(values))
            
            elif isinstance(values, dict):
                await self.cursor.executemany(
                    f"INSERT OR REPLACE INTO {self.table_name} VALUES(?, ?)", 
                    self._value_string(values))

            else:
                raise TypeError(f'values must be of type list, tuple or dict. type={type(values)}')

            await self.sqliteConnection.commit()
        except aiosqlite.Error as error:
            LOG.exception(f'write: {error}')
            raise
        except Exception as error:
            LOG.exception(f'write: {error}')
            raise
        else:
            LOG.debug(f'Write successful, count={len(values)}, table_name={self.table_name}')
            
    async def read(self, node_id: str | list) -> Node | list:
        try:
            if isinstance(node_id, (str, bytes)):
                await self.cursor.execute(
                    f"SELECT * FROM {self.table_name} WHERE node_id=?", 
                    list([node_id]))
                row = await self.cursor.fetchall()
                results = self.Node(*row[0])
                
            elif isinstance(node_id, (list, tuple)):
                await self.cursor.execute(
                    f"SELECT * FROM {self.table_name} WHERE node_id IN ({', '.join('?' for _ in node_id)})", 
                    list(node_id))
                row = await self.cursor.fetchall()
                results = [self.Node(*x) for x in row] 
                
            else:
                raise TypeError(f'values must be of type str, bytes, list or tuple. type={type(node_id)}')

            await self.sqliteConnection.commit()
        except aiosqlite.Error as error:
            LOG.exception(f'read: {error}')
            raise
        except IndexError as error:
            if not row:
                LOG.debug(f'Read returned NONE, node_id={node_id}, table_name={self.table_name}')
                return None
            else:
                LOG.exception(f'read: {error}')
                raise
        except Exception as error:
            LOG.exception(f'read: {error}')
            raise
        else:
            LOG.debug(f'Read successful, node_id={node_id}, table_name={self.table_name}')
            return results
        
    async def node_keys(self) -> list:
        try:
            await self.cursor.execute(f"SELECT node_id FROM {self.table_name}")
            row = await self.cursor.fetchall()
            results = [x[0] for x in row]
            await self.sqliteConnection.commit()
        except aiosqlite.Error as error:
            LOG.exception(f'node_keys: {error}')
            raise
        except Exception as error:
            LOG.exception(f'node_keys: {error}')
            raise
        else:
            LOG.debug(f'Node keys read successful, table_name={self.table_name}')
            return results

    async def delete_node(self, node_id: str) -> None:
        try:
            await self.cursor.execute(
                f"DELETE FROM {self.table_name} WHERE node_id=?", 
                list([node_id]))
            await self.sqliteConnection.commit()
        except aiosqlite.Error as error:
            LOG.exception(f'delete_node: {error}')
            raise
        except Exception as error:
            LOG.exception(f'delete_node: {error}')
            raise
        else:
            LOG.debug(f'Delete node successful, node_id={node_id}, table_name={self.table_name}')

    async def close(self) -> None:
        try:
            await self.cursor.close()
            await self.sqliteConnection.close()
        except aiosqlite.Error as error:
            LOG.exception(f'close: {error}')
            raise
        except Exception as error:
            LOG.exception(f'close: {error}')
            raise
        else:
            LOG.info(f'Connection closed, table_name={self.table_name}')

    def _value_string(self, values: dict) -> list:
        value_store = []
        for k, v in values.items():
            value_store.append((k, v))
        return value_store

# Tests
async def _test_type_write(database: AsyncDataBase) -> None:
    try:
        await database.write('test')
    except TypeError:
        LOG.debug('Type error caught, this is expected.')
        return True
    except Exception as e:
        raise e

async def _test_type_read(database: AsyncDataBase) -> None:
    try:
        await database.read({'test'})
    except TypeError:
        LOG.debug('Type error caught, this is expected.')
        return True
    except Exception as e:
        raise e 

async def test() -> bool:  
    from lib.utilities import CWD
  
    # Test data
    data = {
        '_tuple':('_tuple', b'123'),
        '_list':['_list', b'456'],
        '_dict':{'_dict0': b'789', '_dict1': b'0ab'},
        '_namedtuple':Node('_namedtuple', b'cde'),
    }

    try:
        # Init database then open the connection and create the table
        db = AsyncDataBase('zkp_test_db', 'test_case')
        await db.open_connection()
        await db.create()

        # Write test data
        for v in data.values():
            await db.write(v)
            
        # Test single read
        node = await db.read('_tuple')
        assert node.node == b'123', f'_tuple read failed'

        # Test multi read
        nodes = await db.read(['_list', '_dict0', '_namedtuple'])
        for node in nodes:
            if node.node_id in data:
                assert node.node == data[node.node_id][1], f'{node.node_id} read failed, {node.node}'

        # Test delete and node_keys
        await db.delete_node('_tuple')
        node_keys = await db.node_keys()
        for k in ['_dict0', '_dict1', '_list', '_namedtuple']:
            assert k in node_keys, f'test node_keys failed, {k} not in {node_keys}'

        # Test type error, should return True is error is caught, else raise
        assert await _test_type_write(db)  # Should log error, this is expected
        assert await _test_type_read(db)  # Should log error, this is expected

        # Check read should return None if key not in db
        assert await db.read('not_in_db') == None, 'read not_in_db failed'
        
        # Remove test data
        for k in data.keys():
            await db.delete_node(k)
    
        # Close and delete database
        await db.close()
            
    except Exception as error:
        LOG.exception(f'LRUDataBase Test Failed: {error}', exc_info=True)
        raise
    finally:
        # Remove test database
        db.database_path.unlink()
        LOG.info('AsyncDataBase Test completed successfully.')
        return True


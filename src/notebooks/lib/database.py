from lib.utilities import setup_logging, CWD
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('DataBase')
LOG.setLevel(logging.DEBUG)

import asyncio
import aiosqlite
from pathlib import Path
from collections import namedtuple

Node = namedtuple('Node', ['node_id', 'node'])


class AsyncDataBase:
    sqliteConnection: aiosqlite.Connection

    def __init__(self, name: str, path: str = CWD + 'database/'):
        self.name = name
        self.path = path
        self.database_path = Path(f'{self.path}{self.name}.db')
        self.Node = Node

    async def open_connection(self) -> None:
        try:
            self.sqliteConnection = await aiosqlite.connect(self.database_path)
            self.sqliteConnection.row_factory = aiosqlite.Row
            self.cursor = await self.sqliteConnection.cursor()

        except aiosqlite.Error as error:
            LOG.exception(f'open_connection: {error}')
            raise
        else:
            LOG.info(f'Connection to database "{self.name}" established.')
    
    async def create(self) -> None:
        try:
            await self.cursor.execute(
                f'''CREATE TABLE IF NOT EXISTS {self.name} (
                "node_id" text PRIMARY KEY,
                "node" blob)''')
            await self.sqliteConnection.commit()

        except aiosqlite.Error as error:
            LOG.exception(f'create database table: {error}')
            raise
        else:
            LOG.info(f'Database "{self.name}" successfully created.')
            return None

    async def write(self, values: tuple | dict) -> None:
        try:
            if isinstance(values, (tuple, list)):
                await self.cursor.execute(
                    f"INSERT OR REPLACE INTO {self.name} VALUES(?, ?)", 
                    list(values))
            
            elif isinstance(values, dict):
                await self.cursor.executemany(
                    f"INSERT OR REPLACE INTO {self.name} VALUES(?, ?)", 
                    self._value_string(values))

            else:
                raise TypeError(f'values must be of type list, tuple or dict. type={type(values)}')

            await self.sqliteConnection.commit()

        except aiosqlite.Error as error:
            LOG.exception(f'Database write error: {error}')
            raise
        except Exception as error:
            LOG.exception(f'Database write error: {error}')
            raise
        else:
            LOG.debug(f'Database write successful. count={len(values)}, table_name={self.name}')
            
    async def read(self, node_id: str | list) -> Node | list:
        try:
            if isinstance(node_id, (str, bytes)):
                await self.cursor.execute(
                    f"SELECT * FROM {self.name} WHERE node_id=?", 
                    list([node_id]))
                row = await self.cursor.fetchall()
                results = self.Node(*row[0])
                
            elif isinstance(node_id, (list, tuple)):
                await self.cursor.execute(
                    f"SELECT * FROM {self.name} WHERE node_id IN ({', '.join('?' for _ in node_id)})", 
                    list(node_id))
                row = await self.cursor.fetchall()
                results = [self.Node(*x) for x in row] 
                
            else:
                raise TypeError(f'values must be of type list or tuple. type={type(node_id)}')

            await self.sqliteConnection.commit()

        except aiosqlite.Error as error:
            LOG.exception(f'Database read error: {error}')
            raise
        except IndexError as error:
            if not row:
                LOG.debug(f'Database read returned NONE. node_id={node_id}, table_name={self.name}')
                return None
            else:
                LOG.exception(f'Database read error: {error}')
                raise
        except Exception as error:
            LOG.exception(f'Database read error: {error}')
            raise
        else:
            LOG.debug(f'Database read successful. node_id={node_id}, table_name={self.name}')
            return results
        
    async def node_keys(self) -> list:
        try:
            await self.cursor.execute(f"SELECT node_id FROM {self.name}")
            row = await self.cursor.fetchall()
            results = [x[0] for x in row]
            await self.sqliteConnection.commit()

        except aiosqlite.Error as error:
            LOG.exception(f'Database read node keys error: {error}')
            raise
        else:
            LOG.debug(f'Database read of node keys successful. table_name={self.name}')
            return results

    async def delete_node(self, node_id: str) -> None:
        try:
            await self.cursor.execute(
                f"DELETE FROM {self.name} WHERE node_id=?", 
                list([node_id]))
            await self.sqliteConnection.commit()

        except aiosqlite.Error as error:
            LOG.exception(f'Database delete node error: {error}')
            raise
        else:
            LOG.debug(f'Database delete node successful. node_id={node_id}, table_name={self.name}')

    async def close(self) -> None:
        await self.cursor.close()
        await self.sqliteConnection.close()  
        LOG.info(f'Connection to database closed. name={self.name}')
            
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
        return True
    except Exception as e:
        raise e

async def _test_type_read(database: AsyncDataBase) -> None:
    try:
        await database.read(b'test')
    except TypeError:
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
        db = AsyncDataBase('test_database', CWD + '/database/')
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
        await _test_type_write(db)  # Should log error, this is expected
        await _test_type_read(db)

        # Remove test data
        for k in data.keys():
            await db.delete_node(k)
    
        # Close and delete database
        await db.close()
        db.database_path.unlink()    

    except Exception as error:
        LOG.exception(f'LRUDataBase Test Failed: {error}', exc_info=True)
        print(f'AsyncDataBase error: {error}')
        raise
    finally:
        LOG.info('AsyncDataBase Test completed successfully.')
        return True


'''
The code is a Python class named AsyncDataBase that provides asynchronous 
interaction with a SQLite database.

Copyright (C) 2024  RC Bravo Consuling Inc., https://github.com/rcbravo-dev

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
import aiosqlite
from collections import namedtuple
from pathlib import Path

from lib.utilities import setup_logging, load_yaml
CONFIGS = load_yaml('configs/config.yaml')['Application']
DB_CONFIGS = load_yaml('configs/config.yaml')['DataBase']

logging = setup_logging(path = CONFIGS['loggingConfigPath'])
LOG = logging.getLogger(DB_CONFIGS['logger'])
LOG.setLevel(CONFIGS['logging_level'])

Node = namedtuple('Node', ['node_id', 'node'])
CWD = CONFIGS['CWD']


class AsyncDataBase:
    '''The code is a Python class named AsyncDataBase that provides asynchronous 
    interaction with a SQLite database. This class is designed to be used 
    asynchronously, as indicated by the async keyword in many of its methods.
    
    This class is useful when you want to interact with a SQLite database asynchronously. 
    It provides methods for creating a table, writing to the table, reading from the 
    table, retrieving all keys from the table, deleting a node from the table, and 
    closing the connection to the database.
    '''
    sqliteConnection: aiosqlite.Connection

    def __init__(self, file_name: str, table_name: str, database_path: str = CWD + 'database/') -> None:
        '''This is the constructor method. It initializes the instance with a file name, 
        a table name, and a database path.'''
        self.file_name = file_name
        self.table_name = table_name
        self.database_path = Path(f'{database_path}{file_name}.db')
        self.Node = Node

    async def open_connection(self) -> None:
        '''This method opens a connection to the SQLite database. It also sets the 
        row factory to aiosqlite.Row which allows you to access rows by their column 
        names.'''
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
            LOG.info(f'Connection to "{self.file_name}" established.')
    
    async def create(self) -> None:
        '''This method creates a new table in the database if it doesn't already 
        exist. The table has two columns: "node_id" (text) and "node" (blob).'''
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
        '''This method writes values to the database. The values can be a tuple 
        or list when inserting single key-value pairs, and a dict when inserting 
        multiple key-value pairs.'''
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
        '''This method reads values from the database using a node_id. The node_id 
        can be a string, bytes, list, or tuple.'''
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
        '''This method retrieves all the node_ids from the database.'''
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
        '''This method deletes a node from the database using a node_id.'''
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
        '''This method closes the cursor and the connection to the database.'''
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
        '''This is a helper method that converts a dictionary 
        into a list of tuples. It's used in the write method when 
        inserting multiple key-value pairs into the database.'''
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


# LRUdb
 A Last Recently Used (LRU) Cache that provides asynchronous interaction with a SQLite database.

### Main
The code implements a Least Recently Used (LRU) cache with a backend database. 
The code is used to test the imported LRU and Database using random particle
collisions as an analog for user interaction.

### LRUDataBase
The code is a Python class named LRUDataBase that implements a Least Recently Used (LRU) cache with a backing database. This class is designed to be used asynchronously, as indicated by the async keyword in many of its methods.

Here's a breakdown of the class and its methods:

__init__: This is the constructor method. It initializes the instance with a file name, a table name, and a configuration dictionary.

__aenter__ and __aexit__: These methods are used to make the class compatible with the async context manager protocol (async with statement). __aenter__ connects to the database and __aexit__ closes the connection.

__aiter__ and __anext__: These methods make the class an asynchronous iterable. The __anext__ method retrieves the next key from the database or the LRU cache.

__connect__: This method connects to the database and initializes the LRU cache.

__write__: This method writes a key-value pair to the LRU cache. If the cache is full, it offloads the oldest data to the database.

__read__: This method reads a value from the LRU cache or the database using a key. If the key is not found, it returns None.

__get__: This method retrieves the value of a key from the database or LRU cache. If the key is not found, it returns a default value.

__node_keys__: This method retrieves all the keys from the database.

__delete__: This method deletes a key-value pair from the database and the LRU cache.

__flush_cache__: This method flushes the LRU cache to the database.

__sync__: This method offloads old items from the LRU cache to the database.

__close__: This method flushes the cache to the database and closes the database connection.

__encode_key__, __decode_key__, __serialize__, __un_serialize__: These are helper methods for encoding and decoding keys, and serializing and unserializing values.

This class is useful when you want to cache the most recently used data in memory for quick access, but also want to persist all data in a database for long-term storage.

### LRU
This Python code defines a class LRU which implements a Least Recently Used (LRU) cache as a frontend to the AsyncDataBase.

### AsyncDataBase
The code is a Python class named AsyncDataBase that provides asynchronous interaction with a SQLite database. This class is designed to be used asynchronously, as indicated by the async keyword in many of its methods.

Here's a breakdown of the class and its methods:

__init__: This is the constructor method. It initializes the instance with a file name, a table name, and a database path.

__open_connection__: This method opens a connection to the SQLite database. It also sets the row factory to aiosqlite.Row which allows you to access rows by their column names.

__create__: This method creates a new table in the database if it doesn't already exist. The table has two columns: "node_id" (text) and "node" (blob).

__write__: This method writes values to the database. The values can be a tuple or list when inserting single key-value pairs, and a dict when inserting multiple key-value pairs.

__read__: This method reads values from the database using a node_id. The node_id can be a string, bytes, list, or tuple.

__node_keys__: This method retrieves all the node_ids from the database.

__delete_node__: This method deletes a node from the database using a node_id.

__close__: This method closes the cursor and the connection to the database.

__value_string__: This is a helper method that converts a dictionary into a list of tuples. It's used in the write method when inserting multiple key-value pairs into the database.

This class is useful when you want to interact with a SQLite database asynchronously. It provides methods for creating a table, writing to the table, reading from the table, retrieving all keys from the table, deleting a node from the table, and closing the connection to the database.

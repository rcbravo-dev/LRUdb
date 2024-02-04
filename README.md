# LRUdb
 A Last Recently Used (LRU) Cache that provides asynchronous interaction with a SQLite database.
 
 Initial tests show a marked improvement as the size of the LRU moves up from 20% of database size to 80%.


```
LRUDataBase test passed.

Test of LRU size 20 completed in 3.6643500328063965s
Test of LRU size 40 completed in 1.9051239490509033s
Test of LRU size 80 completed in 1.3680109977722168s

As the LRU size increases, the time to run the simulation decreases:
	LRU size: LRU_20, time: 1.2215, count: 7791, io: 156µsec
	LRU size: LRU_40, time: 0.6350, count: 7791, io: 81µsec
	LRU size: LRU_80, time: 0.4560, count: 7791, io: 58µsec
```


### Caveats 
I have not tested forking this repo yet. I am using this code in an application I am developing so your local imports may not function properly. I develop using Jupyter notebooks, then run a script that pushes the .py and .md code to separate files in the ```src.notebook.lib``` and ```src.markdown``` directories.

### Main
The code is an asynchronous Python function named ```main```. This function simulates a system of particles in a box, with the state of each particle being stored in a Least Recently Used (LRU) cache backed by a SQLite database. The function takes several parameters to configure the simulation and the LRU cache.

Here's a breakdown of the function:

- ```lru_size=100```: The maximum size of the LRU cache.
- ```box_size=50```: The number of particles in the box.
- ```steps=20```: The number of steps to run the simulation for.
- ```dt=1./30```: The time step for the simulation.
- ```bound_size=4```: The size of the box the particles are in.
- ```**kwargs```: Additional keyword arguments. Currently, only 'SEED' is used to seed the random number generator.

The function first creates an instance of ```LRUDataBase``` named shelf and connects to it. It then initializes the state of the particles in the box and writes this initial state to the shelf.

The function then enters a loop to run the simulation. In each step of the simulation, it reads the state of certain particles from the shelf, updates the state of the particles in the box, and then writes the new state of certain particles back to the shelf.

After the simulation is complete, the function closes the shelf and deletes the SQLite database file.

The function returns the total number of read and write operations performed on the shelf.

This function demonstrates how to use an LRU cache backed by a SQLite database to manage the state of a system in a simulation. The state of the system can be larger than the size of the LRU cache, as old data is offloaded to the SQLite database when the cache becomes full. This allows the simulation to handle systems that would not fit into memory if all state data was kept in the cache.

### LRUDataBase
The code is a Python class named ```LRUDataBase``` that implements a Least Recently Used (LRU) cache with a backing database. This class is designed to be used asynchronously, as indicated by the async keyword in many of its methods.

Here's a breakdown of the class and its methods:

- ```__init__```: This is the constructor method. It initializes the instance with a file name, a table name, and a configuration dictionary.

- ```__aenter__``` and ```__aexit__```: These methods are used to make the class compatible with the async context manager protocol (async with statement). ```__aenter__``` connects to the database and ```__aexit__``` closes the connection.

- ```__aiter__``` and ```__anext__```: These methods make the class an asynchronous iterable. The ```__anext__``` method retrieves the next key from the database or the LRU cache.

- ```__connect__```: This method connects to the database and initializes the LRU cache.

- ```__write__```: This method writes a key-value pair to the LRU cache. If the cache is full, it offloads the oldest data to the database.

- ```__read__```: This method reads a value from the LRU cache or the database using a key. If the key is not found, it returns None.

- ```__get__```: This method retrieves the value of a key from the database or LRU cache. If the key is not found, it returns a default value.

- ```__node_keys__```: This method retrieves all the keys from the database.

- ```__delete__```: This method deletes a key-value pair from the database and the LRU cache.

- ```__flush_cache__```: This method flushes the LRU cache to the database.

- ```__sync__```: This method offloads old items from the LRU cache to the database.

- ```__close__```: This method flushes the cache to the database and closes the database connection.

- ```__encode_key__```, ```__decode_key__```, ```__serialize__```, ```__un_serialize__```: These are helper methods for encoding and decoding keys, and serializing and unserializing values.

This class is useful when you want to cache the most recently used data in memory for quick access, but also want to persist all data in a database for long-term storage.

### LRU
This Python code defines a class ```LRU``` which implements a Least Recently Used (LRU) cache as a frontend to the AsyncDataBase.

### AsyncDataBase
The code is a Python class named ```AsyncDataBase``` that provides asynchronous interaction with a SQLite database. This class is designed to be used asynchronously, as indicated by the async keyword in many of its methods.

Here's a breakdown of the class and its methods:

- ```__init__```: This is the constructor method. It initializes the instance with a file name, a table name, and a database path.

- ```__open_connection__```: This method opens a connection to the SQLite database. It also sets the row factory to aiosqlite.Row which allows you to access rows by their column names.

- ```__create__```: This method creates a new table in the database if it doesn't already exist. The table has two columns: "node_id" (text) and "node" (blob).

- ```__write__```: This method writes values to the database. The values can be a tuple or list when inserting single key-value pairs, and a dict when inserting multiple key-value pairs.

- ```__read__```: This method reads values from the database using a node_id. The node_id can be a string, bytes, list, or tuple.

- ```__node_keys__```: This method retrieves all the node_ids from the database.

- ```__delete_node__```: This method deletes a node from the database using a node_id.

- ```__close__```: This method closes the cursor and the connection to the database.

- ```__value_string__```: This is a helper method that converts a dictionary into a list of tuples. It's used in the write method when inserting multiple key-value pairs into the database.

This class is useful when you want to interact with a SQLite database asynchronously. It provides methods for creating a table, writing to the table, reading from the table, retrieving all keys from the table, deleting a node from the table, and closing the connection to the database.

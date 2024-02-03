'''
The code implements a Least Recently Used (LRU) cache with a backing database. 
The code is used to test the imported LRU and Database using random particle
collisions as an analog for customer interaction.

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
import numpy as np
from pathlib import Path
import time

from src.notebooks.lib.utilities import setup_logging, load_yaml, import_util
CONFIGS = load_yaml('configs/config.yaml')['Application']
MAIN_CONFIGS = load_yaml('configs/config.yaml')['main']
CWD = CONFIGS['CWD']

import_util(cwd=CWD, paths=['src/notebooks', 'src/notebooks/lib'])
from src.notebooks.lib.lru_database import LRUDataBase
from src.notebooks.lib.lru_database import test as lru_test
from src.notebooks.lib.test_case import ParticleBox

logging = setup_logging(path = CONFIGS['loggingConfigPath'])
LOG = logging.getLogger(MAIN_CONFIGS['logger'])
LOG.setLevel(CONFIGS['logging_level'])


async def main(lru_size=100, box_size=50, steps=20, dt=1./30, bound_size=4, **kwargs): 
    count = 0

    # Database
    shelf = LRUDataBase('test_db', 'test_case')
    await shelf.connect()
    shelf.lru._create_empty_deck(lru_size)

    # Particles in a box
    np.random.seed(kwargs.get('SEED', 0))
    
    init_state = -0.5 + np.random.random((box_size, 4))
    init_state[:, :2] *= 3.9
    bounds = [-bound_size, bound_size, -bound_size, bound_size]
    size = (bounds[1] - bounds[0]) * 0.01

    box = ParticleBox(init_state, bounds=bounds, size=size, G=1.0)

    # Initial write to the shelf
    for i, loc in enumerate(init_state):
        await shelf.write(f'pc_{i}', loc)
        count += 1

    if count == box_size:

        # Run the simulation
        for i in range(steps):
            box.step(dt)

            # Read from the shelf
            if box.reads:
                r_keys = [f'pc_{x}' for x in box.reads]
                r = await shelf.read(r_keys)
                count += len(r_keys)
            else:
                pass

            # Write to the shelf
            if box.writes:
                for k, v in box.writes.items():
                    await shelf.write(f'pc_{k}', v)
                    count += 1
            else:
                pass

    # Close the shelf and cleanup
    db_path = Path(shelf.db.database_path)
    await shelf.close()
    Path(db_path).unlink()

    return count

async def main_test():
    if await lru_test():
        print('LRUDataBase test passed.', end='\n\n')
    else:
        print('LRUDataBase test failed.', end='\n\n')

    lru_sizes = [20, 40, 80]
    results = {}

    for lru_size in lru_sizes:
        time_store = []
        count_store = []
        MAIN_CONFIGS['lru_size'] = lru_size

        for trial in range(3):
            
            t = time.time()
            cnt = await main(**MAIN_CONFIGS)
            run_time = time.time() - t

            time_store.append(run_time)
            count_store.append(cnt)

        results[f'LRU_{lru_size}'] = {'time': np.mean(time_store), 'count': np.mean(count_store)}
        print(f'Test of LRU size {lru_size} completed in {sum(time_store)}s')

    print()
    print('As the LRU size increases, the time to run the simulation decreases:')
    for k, v in results.items():
        # Time per read/write
        io_time = int((v["time"] / v["count"]) * 1e6)
        # Results
        print(f'\tLRU size: {k}, time: {v["time"]:.4f}, count: {v["count"]:.0f}, io: {io_time}µsec')



if __name__ == '__main__':
    import asyncio

    try:
        # Python
        asyncio.run(main_test())
    except Exception:
        # Jupyter
        print('Asyncio run failed. Running main_test() in a Jupyter loop.')
        await main_test()

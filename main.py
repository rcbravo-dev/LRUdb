from src.notebooks.lib.utilities import setup_logging, import_util, CWD
import_util(cwd=CWD, paths=['src/notebooks', 'src/notebooks/lib'])
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('application')
LOG.debug('Application log started.')

import numpy as np
from pathlib import Path
import time

from src.notebooks.lib.lru_database import LRUDataBase
from src.notebooks.lib.lru_database import test as lru_test

from src.notebooks.lib.test_case import ParticleBox


async def main(lru_size=100, box_size=50, steps=20, dt=1./30, bound_size=4):
    count = 0

    # Database
    shelf = LRUDataBase('test_db', 'test_case')
    await shelf.connect()
    shelf.lru._create_empty_deck(lru_size)

    # Particles in a box
    np.random.seed(10101010)
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
        # Run the animation
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


# For python
if __name__ == '__main__':
    import asyncio

    if asyncio.run(lru_test()):
        print('LRUDataBase test passed.', end='\n\n')
    else:
        print('LRUDataBase test failed.', end='\n\n')

    lru_sizes = [20, 40, 80]
    results = {}

    for lru_size in lru_sizes:
        time_store = []
        count_store = []
        for trial in range(3):

            t = time.time()
            cnt = asyncio.run(main(lru_size=lru_size, box_size=100, steps=500, dt=1./30, bound_size=2))
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

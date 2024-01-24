import numpy as np
import hashlib
import logging
import logging.config
import yaml

CWD = '/Users/Shared/SharedProjects/Projects/ZeroKnowledge/zkp/'
TRASH = '/Users/code/.Trash/'
LOG_LEVEL = 'DEBUG'
SEED = 1234
RNG = np.random.default_rng(seed=SEED)


def setup_logging(default_path=CWD + '/config/logging_config.yaml'):
    with open(default_path, 'rt') as file:
        config = yaml.safe_load(file.read())
    logging.config.dictConfig(config)

    print('Logging configured in config_zkp.py')


configs = {
	'zkp_abc':{
		'args':[],
		'kwargs':{
            # The size of the secret array. 
			# assert array_size % 8 == 0
			'array_size':32, 
            # The number of bits each element in the secret array will represent.
			# Options are: 8, 16, 32, 64 
			'bits':8,
            # The hashing protocol used.
			# Options are: 'sha256', 'sha512', 'blake2s', 'blake2b'
			'hash_protocol_string':'sha256', 
            # The maximum number of rotations performed IOT randomize the secret array.
			'max_rotations':30,
            'name_size':16,
		}
	},
}



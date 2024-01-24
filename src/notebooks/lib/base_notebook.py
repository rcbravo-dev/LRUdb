from lib.utils import setup_logging
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('notebook')
LOG.debug('notebook log.')


def foo(x):
    return x + 1

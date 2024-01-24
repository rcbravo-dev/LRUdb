from src.notebooks.lib.utilities import setup_logging
logging = setup_logging(path = 'configs/logging_config.yaml')
LOG = logging.getLogger('notebook')
LOG.debug('Notebook log.')




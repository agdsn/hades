from logging.config import fileConfig
import pkg_resources


fileConfig(pkg_resources.resource_filename(__name__, 'logging.ini'),
           disable_existing_loggers=False)

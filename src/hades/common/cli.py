import argparse
import logging
import os
import sys
from gettext import gettext as _

from hades import constants


class ArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass that exists with os.EX_USAGE exit code if parsing
    fails.
    """
    def error(self, message):
        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(os.EX_USAGE, _('%(prog)s: error: %(message)s\n') % args)


parser = ArgumentParser(add_help=False)
parser.add_argument('-c', '--config', default=None, help="Path to config file")
parser.add_argument('-v', '--verbose', dest='verbosity',
                    default=None, action='count', help='Be more verbose')
parser.add_argument('-q', '--quiet', dest='verbosity',
                    action='store_const', const=0, help='Be quiet')
parser.add_argument('-V', '--version', action='version',
                    version=constants.PACKAGE_VERSION)
VERBOSITY_LEVELS = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
DEFAULT_VERBOSITY = 1


def setup_cli_logging(program, args):
    """
    Setup logging for CLI applications, that do not configure logging
    themselves.

    Flask and Celery are quite opinionated about logging, so this function
    should probably not be called in their launchers.
    :param program: The name of the program
    :param args: The parsed arguments of the program
    """
    if args.verbosity is None:
        verbosity = os.environ.get('HADES_VERBOSITY', DEFAULT_VERBOSITY)
        try:
            verbosity = int(verbosity)
        except ValueError:
            verbosity = DEFAULT_VERBOSITY
    else:
        verbosity = args.verbosity
    effective_verbosity = min(max(verbosity, -len(VERBOSITY_LEVELS)),
                              len(VERBOSITY_LEVELS) - 1)
    level = VERBOSITY_LEVELS[effective_verbosity]
    logging.basicConfig(level=level, style='%',
                        format="{} %(levelname)-8s %(asctime)s "
                               "%(name)-15s %(message)s".format(program),
                        stream=sys.stderr)

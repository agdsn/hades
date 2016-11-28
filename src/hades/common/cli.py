import argparse
import os
import sys
from gettext import gettext as _

from hades import constants


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(os.EX_USAGE, _('%(prog)s: error: %(message)s\n') % args)


parser = ArgumentParser(add_help=False)
parser.add_argument('-c', '--config', type=argparse.FileType('rb'),
                    default=None, help="Path to config file")
parser.add_argument('-V', '--version', action='version',
                    version=constants.PACKAGE_VERSION)

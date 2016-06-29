import collections
import logging
import re

import netaddr

logger = logging.getLogger(__name__)
shell_types = (int, str, bool, netaddr.IPAddress, netaddr.IPNetwork)
pattern = re.compile(r'([^a-zA-Z0-9_])')
replacement = r'\\\1'


def escape(value):
    """
    Escape a string for shell argument use.
    shlex.quote breaks unfortunately on certain strings
    """
    return pattern.sub(replacement, str(value))


def export(config, output_format, file):
    """
    Export config as shell variables.
    :param config: Configuration to export
    :param output_format: One of systemd, posix, bash, zsh
    :param file: File-like object
    """
    mappings = output_format in ('bash', 'ksh', 'zsh')
    sequences = output_format in ('bash', 'ksh', 'zsh')
    for name, value in config.items():
        name = escape(name)
        if isinstance(value, shell_types):
            print("{}={}".format(name, escape(value)), file=file)
        elif isinstance(value, collections.Mapping) and mappings:
            if output_format == 'bash':
                print("declare -A {}".format(name), file=file)
            if output_format in ('ksh', 'zsh'):
                print("typeset -A {}".format(name), file=file)
            value = ' '.join("[{}]={}".format(escape(k), escape(v))
                             for k, v in value.items()
                             if isinstance(k, shell_types) and
                             isinstance(v, shell_types))
            print("{}=({})".format(name, value), file=file)
        elif isinstance(value, collections.Sequence) and sequences:
            value = ' '.join(escape(v) for v in value
                             if isinstance(v, shell_types))
            print("{}=({})".format(name, value), file=file)

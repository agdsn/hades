import collections
import itertools
import os
import os.path
import shutil
import sys
from functools import partial

import jinja2
import netaddr
import pkg_resources
from jinja2.exceptions import FilterArgumentError
from jinja2.filters import environmentfilter

from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.loader import load_config


def template_filter(name):
    def decorator(f):
        template_filter.registered[name] = f
        return f
    return decorator
template_filter.registered = dict()


@template_filter('unique')
def do_unique(a):
    return set(a)


@template_filter('intersection')
def do_intersection(a, b):
    return set(a).intersection(set(b))


@template_filter('difference')
def do_difference(a, b):
    return set(a).difference(set(b))


@template_filter('symmetric_difference')
def do_symmetric_difference(a, b):
    return set(a).symmetric_difference(set(b))


@template_filter('union')
def do_union(a, b):
    return set(a).union(set(b))


@template_filter('min')
def do_min(a):
    return min(a)


@template_filter('max')
def do_max(a):
    return max(a)


@template_filter('sorted')
@environmentfilter
def do_sorted(env, iterable, *, attribute=None, item=None, reverse=False):
    if attribute is None and item is None:
        key = None
    elif attribute is not None and item is not None:
        raise FilterArgumentError("Only one of attribute and item may be"
                                  "specified")
    elif attribute is not None:
        key = partial(env.getattr, attribute=attribute)
    elif item is not None:
        key = partial(env.getitem, argument=item)
    return sorted(iterable, key=key, reverse=reverse)


@template_filter('zip')
def do_zip(*iterables):
    return zip(*iterables)


@template_filter('zip_longest')
def do_zip_longest(*iterables, fillvalue=None):
    return itertools.zip_longest(*iterables, fillvalue=fillvalue)


@template_filter('dirname')
def do_dirname(a):
    return os.path.dirname(a)


class ConfigGenerator(object):
    TEMPLATE_SUFFIX = ".j2"

    def __init__(self, template_dir, config):
        self.config = config
        self.template_dir = template_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            auto_reload=False, autoescape=False, keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
            extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols',
                        'jinja2.ext.with_'],
        )
        self.env.globals.update({
            'collections': collections,
            'itertools': itertools,
            'netaddr': netaddr,
            'dirname': os.path.dirname
        })
        self.env.filters.update(template_filter.registered)

    def from_directory(self, name, target_dir):
        source_base = os.path.join(self.template_dir, name)
        sources = collections.deque()
        sources.append(source_base)
        while sources:
            source = sources.pop()
            relpath = os.path.relpath(source, source_base)
            target = os.path.normpath(os.path.join(target_dir, relpath))
            if os.path.isdir(source):
                sources.extend(map(partial(os.path.join, source),
                                   os.listdir(source)))
                if not os.path.exists(target):
                    os.mkdir(target)
            else:
                if source.endswith(self.TEMPLATE_SUFFIX):
                    template_name = os.path.relpath(source, self.template_dir)
                    template = self.env.get_template(template_name)
                    target = target[:-len(self.TEMPLATE_SUFFIX)]
                    with open(target, 'w', encoding='UTF-8') as f:
                        stream = template.stream(BASE_DIRECTORY=target_dir,
                                                 TARGET=target, **self.config)
                        f.writelines(stream)
                else:
                    shutil.copy(source, target)

    def from_file(self, name, output):
        target = os.path.join(self.template_dir, name)
        base_directory = os.path.dirname(target)
        stream = self.env.get_template(name).stream(
            BASE_DIRECTORY=base_directory, TARGET=target, **self.config)
        output.writelines(stream)


def main():
    parser = ArgumentParser(parents=[common_parser])
    parser.add_argument(dest='source', metavar='SOURCE',
                        help="Template file name or template directory name")
    parser.add_argument(dest='destination', metavar='DESTINATION', nargs='?',
                        help="Destination file or directory (default is stdout"
                             "for files; required for directories)")
    args = parser.parse_args()
    config = load_config(args.config)
    template_dir = pkg_resources.resource_filename('hades.config', 'templates')
    generator = ConfigGenerator(template_dir, config)
    source_path = os.path.join(template_dir, args.source)
    if os.path.isdir(source_path):
        generator.from_directory(args.source, args.destination)
    elif os.path.isfile(source_path):
        if args.destination is None:
            generator.from_file(args.source, sys.stdout)
        else:
            with open(args.destination, 'w', encoding='utf-8') as f:
                generator.from_file(args.source, f)
    else:
        print("No such file or directory {} in {}".format(args.source,
                                                          template_dir),
              file=sys.stderr)
        return os.EX_NOINPUT


if __name__ == '__main__':
    sys.exit(main())

import collections
import itertools
import os
import os.path
import shutil
from functools import partial

import jinja2
import netaddr
from jinja2.exceptions import FilterArgumentError
from jinja2.filters import environmentfilter

from hades import constants


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
            'dirname': os.path.dirname,
            'constants': constants,
        })
        self.env.filters.update(template_filter.registered)

    def from_directory(self, name, target_dir):
        source_base = os.path.join(self.template_dir, name)
        sources = collections.deque()
        sources.append(source_base)
        for name in os.listdir(target_dir):
            path = os.path.join(target_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        while sources:
            source = sources.pop()
            relpath = os.path.relpath(source, source_base)
            target = os.path.normpath(os.path.join(target_dir, relpath))
            if os.path.isdir(source):
                sources.extend(map(partial(os.path.join, source),
                                   os.listdir(source)))
                if not os.path.exists(target):
                    os.mkdir(target)
                    shutil.copystat(source, target)
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
                    shutil.copy2(source, target, follow_symlinks=False)

    def from_file(self, name, output):
        target = os.path.join(self.template_dir, name)
        base_directory = os.path.dirname(target)
        stream = self.env.get_template(name).stream(
            BASE_DIRECTORY=base_directory, TARGET=target, **self.config)
        output.writelines(stream)

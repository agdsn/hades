import collections
import io
import itertools
import os
import os.path
import pathlib
import shutil
import sys
from functools import partial
from typing import Optional, TextIO, Union

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

    def __init__(self, template_dir: Union[str, pathlib.PurePath],
                 config):
        self.config = config
        self.template_dir = pathlib.Path(template_dir)
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            auto_reload=False, autoescape=False, keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
            extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols',
                        'jinja2.ext.with_'],
            trim_blocks=True, lstrip_blocks=True,
        )
        self.env.globals.update({
            'collections': collections,
            'itertools': itertools,
            'netaddr': netaddr,
            'dirname': os.path.dirname,
            'constants': constants,
        })
        self.env.filters.update(template_filter.registered)

    def generate(self, source: Union[str, pathlib.PurePath],
                 destination: Optional[Union[str, pathlib.PurePath]]):
        source = pathlib.Path(source)
        if source.is_absolute():
            raise ValueError("Source {} must be a relative path"
                             .format(source))
        source = self.template_dir / source
        if not source.exists():
            raise ValueError("No file or directory named {} found in {}"
                             .format(str(source), self.template_dir)) from None
        if source.is_dir():
            if destination is None:
                raise ValueError("Destination can't be stdout, if source is"
                                 "a directory")
            destination = pathlib.Path(destination)
            self._do_generate_directory(source, destination)
        else:
            self._do_generate_file(source, destination)

    def generate_directory(self, source: Union[str, pathlib.PurePath],
                           destination: Union[str, pathlib.PurePath]):
        source = pathlib.PurePath(source)
        if source.is_absolute():
            raise ValueError("Source {} must be a relative path"
                             .format(source))
        source_base = self.template_dir / pathlib.Path(source)
        destination_base = pathlib.Path(destination)
        self._do_generate_directory(source_base, destination_base)

    def _do_generate_directory(self, source_base: pathlib.Path,
                               destination_base: pathlib.Path):
        sources = collections.deque()
        sources.append(source_base)
        # Clear destination directory contents
        for path in destination_base.iterdir():
            if path.is_dir():
                shutil.rmtree(str(path))
            else:
                path.unlink()
        while sources:
            source = sources.pop()
            destination = destination_base / source.relative_to(source_base)
            if source.is_symlink():
                self._create_symlink(source, destination)
            elif source.is_dir():
                sources.extend(source.iterdir())
                if destination.exists():
                    # Clear destination directory contents
                    if destination.is_symlink() or not destination.is_dir():
                        raise ValueError("Destination {} is not a directory"
                                         .format(destination))
                    for path in destination.iterdir():
                        if path.is_dir():
                            shutil.rmtree(str(path))
                        else:
                            path.unlink()
                else:
                    destination.mkdir(exist_ok=True)
                shutil.copystat(str(source), str(destination),
                                follow_symlinks=False)
            else:
                if source.suffix == self.TEMPLATE_SUFFIX:
                    destination = destination.with_name(destination.stem)
                    self._generate_template_to_file(source, destination)
                else:
                    self._copy_to_file(source, destination)

    def generate_file(self, source: Union[str, pathlib.PurePath],
                      destination: Optional[Union[str, pathlib.Path]]):
        source = pathlib.Path(source)
        if source.is_absolute():
            raise ValueError("Source {} must be a relative path"
                             .format(source))
        source = self.template_dir / source
        if not source.exists():
            raise ValueError("File {} not found".format(source)) from None
        if not source.is_file() and not source.is_symlink():
            raise ValueError("{} is not a file".format(source))
        if destination is not None:
            destination = pathlib.Path(destination)
        self._do_generate_file(source, destination)

    def _do_generate_file(self, source: pathlib.Path,
                          destination: Optional[pathlib.Path]):
        if destination is None:
            if source.suffix == self.TEMPLATE_SUFFIX:
                self._generate_template_to_stdout(source)
            else:
                self._copy_to_stdout(source)
        else:
            if source.is_symlink():
                self._create_symlink(source, destination)
            elif source.suffix == self.TEMPLATE_SUFFIX:
                if destination.is_dir():
                    destination = destination / source.stem
                self._generate_template_to_file(source, destination)
            else:
                if destination.is_dir():
                    destination = destination / source.name
                self._copy_to_file(source, destination)

    def _create_symlink(self, source: pathlib.Path, destination: pathlib.Path):
        target = pathlib.Path(os.readlink(str(source)))
        destination.symlink_to(target)

    def _copy_to_file(self, source: pathlib.Path, destination: pathlib.Path):
        shutil.copy2(str(source), str(destination), follow_symlinks=False)

    def _copy_to_stdout(self, source: pathlib.Path):
        self._copy_to_fd(source, sys.stdout.fileno())

    def _copy_to_fd(self, source: pathlib.Path, fd: int):
        with source.open('r') as file:
            end = file.seek(0, io.SEEK_END)
            os.sendfile(fd, file.fileno(), 0, end)

    def _create_file(self, name: pathlib.Path) -> int:
        flags = os.O_WRONLY | os.O_CLOEXEC | os.O_EXCL | os.O_CREAT
        return os.open(str(name), flags)

    def _generate_template_to_file(self, source: pathlib.Path,
                                   destination: pathlib.Path):
        destination = pathlib.Path(destination)
        # Safely create file:
        # 1. Create with O_CREAT | O_EXCL
        # 2. Unlink if fails
        # 3. Try again
        try:
            fd = self._create_file(destination)
        except FileExistsError:
            destination.unlink()
            fd = self._create_file(destination)
        with os.fdopen(fd, mode='w', encoding='utf-8') as writer:
            self._generate_template_to_writer(
                source, writer, destination_dir=destination.parent,
                destination=destination)

    def _generate_template_to_stdout(self, source: pathlib.Path):
        self._generate_template_to_writer(source, sys.stdout)

    def _generate_template_to_writer(self, source: pathlib.Path,
                                     writer: TextIO, **extra_variables):
        template_name = str(source.relative_to(self.template_dir))
        try:
            template = self.env.get_template(template_name)
        except jinja2.TemplateNotFound as e:
            raise ValueError("Template {} not found in {}"
                             .format(template_name, self.template_dir)) from e
        relative_source = source.relative_to(self.template_dir)
        stream = template.stream(**self.config, **extra_variables,
                                 source_base=self.template_dir,
                                 source=relative_source,
                                 source_dir=relative_source.parent)
        writer.writelines(stream)

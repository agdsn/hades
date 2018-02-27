import collections
import grp
import io
import itertools
import logging
import operator
import os
import os.path
import pathlib
import shutil
import stat
import sys
from functools import partial
from typing import Optional, Union, Iterable, Iterator, TextIO, Tuple

import jinja2
import netaddr
from jinja2.exceptions import FilterArgumentError
from jinja2.filters import environmentfilter

from hades import constants

logger = logging.getLogger(__name__)


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


PathArg = Union[str, pathlib.PurePath]


def yield_all_sources(*search_path: pathlib.Path) -> Iterator[
        Tuple[pathlib.Path, pathlib.Path]]:
    """Find all files in the directories on ``search_path``.

    The algorithm is similar to systemd's unit search or the shell's ``PATH``
    search algorithm.

    The directories on the search path are recursively walked in parallel.
    Directories at the beginning of ``search_path`` take precedence over later
    directories, thus for files with the same name, the version in the
    leftmost directory that contains the file is selected. The content of
    directories is merged.

    Symbolic links are never followed and the path of symbolic link is returned
    instead of the path of its target.

    Symbolic links to ``/dev/null`` are handled specially and denote a
    *deletion marker*, that indicates that a file or directory should not be
    included. For directories this means that no directories and their contents
    to the right of the respective directory in the search path should be
    included. Version of the directory and their contents that are on the search
    path to the left of the deletion marker are still included.

    The kind of paths that are returned depend on the kind of paths, that are
    passed as ``search_path``. Relative search path components will yield
    relative paths and absolute components absolute paths.

    :param search_path: A list of paths to directories
    :return: An iterator that yields pairs, where the first element is the
     component of ``search_path``, where the file was found and the second
     element is the path of the file.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Searching for all sources in %s",
                     ', '.join(map(str, search_path)))
    # Perform a bread-first search via a queue.
    # The queue contains a sequence of (search-path, file) pairs for each
    # version of a file on the search path
    queue = collections.deque()
    queue.appendleft(tuple(zip(search_path, search_path)))
    while queue:
        sources = queue.pop()
        if not sources:
            raise ValueError("No search paths")
        else:
            relative_source = sources[0][1].relative_to(sources[0][0])

        # If the current file is a directory, we collect all versions of it in
        # a list, for all other elements we break the loop and continue with the
        # next element. If an error occurs we continue with the next version of
        # the file instead.
        directories = []
        for base, source in sources:
            if source.is_symlink():
                target = os.readlink(str(source))
                # Check for deletion marker
                if target != os.path.devnull:
                    if directories:
                        logger.error("%s is a symlink, while %s is a directory",
                                     source, directories[-1][1])
                        continue
                    else:
                        logger.debug("Found symlink %s to %s in %s",
                                     relative_source, target, base)
                        yield base, source
                else:
                    logging.debug("Skipping %s due to deletion marker in %s",
                                  relative_source, base)
                break
            elif source.is_dir():
                logger.debug("Found directory %s in %s", relative_source, base)
                directories.append(
                    (base, source, {
                        child.name: child
                        for child in source.iterdir()
                    })
                )
            elif source.is_file():
                logger.debug("Found file %s in %s", relative_source, base)
                if directories:
                    logger.error("%s is not a directory, while %s is",
                                 source, directories[-1])
                    continue
                yield base, source
                break
            else:
                logger.error("%s must be a regular file, directory, or symlink",
                             source)
                continue

        if directories:
            if logger.isEnabledFor(logging.DEBUG):
                dir_names = ', '.join(
                    str(base) for base, directory, children in directories)
                logger.debug("Descending into %s in %s",
                             relative_source, dir_names)
            # Merge all names of children
            names = set(itertools.chain(*(
                children.keys()
                for base, directory, children in directories
            )))
            for name in names:
                queue.appendleft(tuple(
                    (base, children[name])
                    for base, directory, children in directories
                    if name in children
                ))
            yield directories[0][:2]


def yield_all_versions(name: pathlib.PurePath,
                       *search_path: pathlib.Path) -> Iterator[
        Tuple[pathlib.Path, pathlib.Path]]:
    """Find all versions of `name` on `search_path`.

    The principle behind the search algorithm are the same as
    :func:`yield_all_sources`. This function however will search for a single
    file or directory named ``name`` and return all versions of ``name`` that
    can be found on the ``search_path``. The version with the highest precedence
    (i.e. from the leftmost component of ``search_path`` that contains a version
    of ``name``) will be returned first.

    :param name: The name of the file or directory
    :param search_path: A list of of paths to directories
    :return: An iterator that yields pairs, where the first element is the
     component of ``search_path``, where the file was found and the second
     element is the path of the file.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Searching for versions of %s in %s", name,
                     ', '.join(map(str, search_path)))
    if not search_path:
        raise ValueError("Empty search path")

    for directory in search_path:
        filename = directory
        # Check for invalid components and /dev/null deletion markers in all
        # components of the path
        for idx, part in enumerate(name.parts):
            if filename.is_symlink():
                raise ValueError("Intermediate components can't be symbolic "
                                 "links")
            if part == os.path.pardir or part == os.path.sep:
                raise ValueError("Illegal component {!r} at index {} of path {}"
                                 .format(part, idx, name))
            filename = filename / part
            # Abort search if deletion marker found
            if (filename.is_symlink() and
                    os.readlink(str(filename)) == os.path.devnull):
                logger.debug("Skipping %s due to deletion marker at %s",
                             directory, filename)
                return
            if not filename.exists() and not filename.is_symlink():
                break
        # Yield if no break occurred
        else:
            logger.debug("Found version of %s in %s at %s",
                         name, directory, filename)
            yield directory, filename


class OverridableFileSystemLoader(jinja2.BaseLoader):
    """A Jinja2 loader that loads templates with the :func:`yield_all_sources`
    algorithm, if the template name is a relative.

    The loader accepts :class:`pathlib.PurePath` objects in addition to strings
    to identify templates.
    """

    def __init__(self, search_paths, encoding='utf-8', template_suffix='.j2'):
        self.search_paths = search_paths
        self.encoding = encoding
        self.template_suffix = template_suffix

    def get_source(self, environment: jinja2.Environment,
                   template: str):
        template = pathlib.Path(template)
        if not template.is_absolute():
            try:
                base, template = next(yield_all_versions(template,
                                                         *self.search_paths))
            except StopIteration:
                raise jinja2.TemplateNotFound(template.name) from None
        try:
            with template.open('r', encoding=self.encoding) as f:
                contents = f.read()
        except (FileNotFoundError, IsADirectoryError):
            raise jinja2.TemplateNotFound(template.name)

        mtime = template.stat().st_mtime

        def has_changed():
            """Checks whether the template loaded via
            :class:`OverridableFileSystemLoader` has changed.

            This function won't detect new versions of the template in other
            search paths with higher precedence or new deletion markers in other
            search paths. We would additionally need a list of all parent
            directories in the other search paths and check all of them."""
            try:
                return template.stat().st_mtime == mtime
            except OSError:
                return False

        return contents, str(template), has_changed

    def list_templates(self):
        return set(str(path.relative_to(base))
                   for base, path in yield_all_sources(*self.search_paths)
                   if not path.is_symlink() and path.is_file()
                   and path.suffix == self.template_suffix)


class GeneratorError(Exception):
    pass


class ConfigGenerator(object):
    TEMPLATE_SUFFIX = ".j2"

    def __init__(self, template_dirs: Union[PathArg, Iterable[PathArg]],
                 config, mode: int = 0o0750,
                 group: Optional[grp.struct_group] = None):
        self.group = group
        mode = stat.S_IMODE(mode)
        # The mode could be masked with much less characters.
        # The verbosity of these statements is for clarity and documentation.
        # Allow only read, write, sticky, and setgid for directories
        self.dir_mode = mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH |
                                stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH |
                                stat.S_ISVTX | stat.S_ISGID)
        # Set execution bits if corresponding read bits are set
        self.dir_mode |= stat.S_IXUSR if stat.S_IRUSR else 0
        self.dir_mode |= stat.S_IXGRP if stat.S_IRGRP else 0
        self.dir_mode |= stat.S_IXOTH if stat.S_IROTH else 0
        # Allow only read, write, and sticky for files
        self.file_mode = mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH |
                                 stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH |
                                 stat.S_ISVTX)
        self.config = config
        if isinstance(template_dirs, (pathlib.PurePath, str)):
            template_dirs = (template_dirs, )
        self.template_dirs = tuple(pathlib.Path(template_dir).resolve()
                                   for template_dir in template_dirs)
        self.env = jinja2.Environment(
            loader=OverridableFileSystemLoader(
                self.template_dirs,
                template_suffix=self.TEMPLATE_SUFFIX
            ),
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

    def _format_search_path(self):
        return ':'.join(map(str, self.template_dirs))

    def _setgroup(self, destination: pathlib.Path):
        if self.group is not None:
            os.chown(str(destination), -1, self.group.gr_gid,
                     follow_symlinks=False)

    def _setstat(self, destination: pathlib.Path, mode: int):
        destination.chmod(mode)
        self._setgroup(destination)

    def generate(self, source: PathArg, destination: Optional[PathArg]):
        source = pathlib.PurePath(source)
        sources = tuple(yield_all_versions(source, *self.template_dirs))
        if not sources:
            raise GeneratorError("No file or directory named {} found "
                                 "(search path: {})"
                                 .format(str(source),
                                         self._format_search_path())) from None
        base, source = sources[0]
        if source.is_dir():
            if destination is None:
                raise GeneratorError("Destination can't be stdout, if source "
                                     "is a directory")
            destination = pathlib.Path(destination)
            search_path = tuple(map(operator.itemgetter(1), sources))
            self._do_generate_directory(search_path, destination)
        else:
            self._do_generate_file(base, source, destination)

    def generate_directory(self, source: PathArg, destination: PathArg):
        source = pathlib.PurePath(source)
        if source.is_absolute():
            raise GeneratorError("Source {} must be a relative path"
                                 .format(source))
        sources = tuple(map(operator.itemgetter(1), yield_all_versions(source)))
        if not sources:
            raise GeneratorError("No directory named {} found (search path {})"
                                 .format(source, self._format_search_path()))
        destination = pathlib.Path(destination)
        self._do_generate_directory(sources, destination)

    def _do_generate_directory(self, sources: Tuple[pathlib.Path, ...],
                               destination: pathlib.Path):
        destination_base = destination
        logger.info("Generating %s from %s", destination,
                    ', '.join(map(str, sources)))
        for base, source in yield_all_sources(*sources):
            destination = destination_base / source.relative_to(base)
            if source.is_symlink():
                self._create_symlink(source, destination)
            elif source.is_dir():
                if destination.exists():
                    logger.debug("Clearing directory %s", destination)
                    # Clear destination directory contents
                    if destination.is_symlink() or not destination.is_dir():
                        raise GeneratorError("Destination {} is not a directory"
                                             .format(destination))
                    for path in destination.iterdir():
                        if path.is_dir():
                            shutil.rmtree(str(path))
                        else:
                            path.unlink()
                else:
                    logger.debug("Creating directory %s", destination)
                    destination.mkdir(self.dir_mode, exist_ok=True)
                shutil.copystat(str(source), str(destination),
                                follow_symlinks=False)
                self._setstat(destination, self.dir_mode)
            else:
                if source.suffix == self.TEMPLATE_SUFFIX:
                    destination = destination.with_name(destination.stem)
                    self._generate_template_to_file(base, source, destination)
                else:
                    self._copy_to_file(source, destination)

    def generate_file(self, source: PathArg, destination: Optional[PathArg]):
        source = pathlib.PurePath(source)
        try:
            base, source = next(yield_all_versions(source, *self.template_dirs))
        except StopIteration:
            raise GeneratorError("File {} not found (search path {})"
                                 .format(source, self._format_search_path())
                                 ) from None
        if not source.is_file() and not source.is_symlink():
            raise GeneratorError("{} is not a file".format(source))
        destination = pathlib.Path(destination)
        self._do_generate_file(base, source, destination)

    def _do_generate_file(self, base: pathlib.Path, source: pathlib.Path,
                          destination: Optional[pathlib.Path]):
        if destination is None:
            if source.suffix == self.TEMPLATE_SUFFIX:
                self._generate_template_to_stdout(base, source)
            else:
                self._copy_to_stdout(source)
        else:
            destination = pathlib.Path(destination)
            if source.is_symlink():
                self._create_symlink(source, destination)
            elif source.suffix == self.TEMPLATE_SUFFIX:
                if destination.is_dir():
                    destination = destination / source.stem
                self._generate_template_to_file(base, source, destination)
            else:
                if destination.is_dir():
                    destination = destination / source.name
                self._copy_to_file(source, destination)

    def _create_symlink(self, source: pathlib.Path, destination: pathlib.Path):
        target = pathlib.Path(os.readlink(str(source)))
        logger.debug("Creating symlink %s to %s", destination, target)
        destination.symlink_to(target)
        self._setgroup(destination)

    def _copy_to_file(self, source: pathlib.Path, destination: pathlib.Path):
        logger.debug("Copying %s to %s", source, destination)
        shutil.copy2(str(source), str(destination), follow_symlinks=False)
        self._setstat(destination, self.file_mode)

    def _copy_to_stdout(self, source: pathlib.Path):
        logger.debug("Copying %s to stdout", source)
        self._copy_to_fd(source, sys.stdout.fileno())

    def _copy_to_fd(self, source: pathlib.Path, fd: int):
        with source.open('r') as file:
            end = file.seek(0, io.SEEK_END)
            os.sendfile(fd, file.fileno(), 0, end)

    def _create_file(self, name: pathlib.Path) -> int:
        flags = os.O_WRONLY | os.O_CLOEXEC | os.O_EXCL | os.O_CREAT
        return os.open(str(name), flags, mode=self.file_mode)

    def _generate_template_to_file(self, base: pathlib.Path,
                                   source: pathlib.Path,
                                   destination: pathlib.Path):
        destination = pathlib.Path(destination)
        # Safely create file:
        # 1. Create with O_CREAT | O_EXCL
        # 2. Unlink if fails
        # 3. Try again
        logger.info("Creating %s from template %s", destination, source)
        try:
            fd = self._create_file(destination)
        except FileExistsError:
            destination.unlink()
            fd = self._create_file(destination)
        self._setgroup(destination)
        with os.fdopen(fd, mode='w', encoding='utf-8') as writer:
            self._generate_template_to_writer(
                base, source, writer,
                destination_dir=destination.parent,
                destination=destination)

    def _generate_template_to_stdout(self, base: pathlib.Path,
                                     source: pathlib.Path):
        logger.info("Instantiating template %s", source)
        self._generate_template_to_writer(base, source, sys.stdout)

    def _generate_template_to_writer(self, base: pathlib.Path,
                                     source: pathlib.Path,
                                     writer: TextIO, **extra_variables):
        try:
            template = self.env.get_template(str(source))
        except jinja2.TemplateNotFound as e:
            raise GeneratorError("Template {} not found (search path {})"
                                 .format(source,
                                         self._format_search_path())
                                 ) from e
        relative_source = source.relative_to(base)
        stream = template.stream(**self.config, **extra_variables,
                                 source_base=base,
                                 source=relative_source,
                                 source_dir=relative_source.parent)
        writer.writelines(stream)

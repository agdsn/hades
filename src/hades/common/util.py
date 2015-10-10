import collections
import functools
from functools import reduce
import operator


def memoize(f):
    f._cache = None

    @functools.wraps(f)
    def wrapper():
        if f._cache is None:
            f._cache = f()
        return f._cache

    return wrapper


class frozendict(collections.Mapping):
    def __init__(self, mapping_or_iterable=None, **kwargs):
        if mapping_or_iterable is None:
            self.__dict = dict(**kwargs)
        else:
            self.__dict = dict(mapping_or_iterable, **kwargs)
        self.__hash = reduce(operator.xor, map(hash, self.__dict.items()), 0)
        self.__init__ = None

    def __contains__(self, x):
        return x in self.__dict

    def __getitem__(self, key):
        return self.__dict[key]

    def __iter__(self):
        return iter(self.__dict)

    def __len__(self):
        return len(self.__dict)

    def __repr__(self):
        class_ = type(self)
        return '{}.{}({!r})'.format(class_.__module__, class_.__name__,
                                    self.__dict)

    def __eq__(self, other):
        return self.__dict == other

    def __ne__(self, other):
        return self.__dict != other

    def __hash__(self):
        return self.__hash

    def copy(self):
        return type(self)(self.__dict)

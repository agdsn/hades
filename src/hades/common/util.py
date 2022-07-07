from __future__ import annotations


def qualified_name(type_):
    if type_.__module__ is None or type_.__module__ == 'builtins':
        return type_.__qualname__
    else:
        return type_.__module__ + '.' + type_.__qualname__

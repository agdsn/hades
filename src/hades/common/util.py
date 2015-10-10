import functools


def memoize(f):
    f._cache = None

    @functools.wraps(f)
    def wrapper():
        if f._cache is None:
            f._cache = f()
        return f._cache

    return wrapper

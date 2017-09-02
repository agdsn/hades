import collections
from flask.sessions import SessionInterface, SessionMixin


class NullSession(collections.MutableMapping, SessionMixin):
    """
    A session similar to the Flask's :class:`flask.sessions.NullSession`, but
    with a different error message.
    """
    __slots__ = ()

    def __len__(self):
        return 0

    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    @staticmethod
    def _fail(*args, **kwargs):
        raise RuntimeError("Sessions are not supported.")

    __delitem__ = __setitem__ = _fail


class NullSessionInterface(SessionInterface):
    def open_session(self, app, request):
        return NullSession()

    def save_session(self, app, session, response):
        pass

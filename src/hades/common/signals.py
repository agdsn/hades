import contextlib
import signal
import types
from typing import Any, Callable, Iterable, Optional


@contextlib.contextmanager
def install_handler_single(
    signum: signal.Signals,
    handler: Callable[[int, Optional[types.FrameType]], Any],
):
    previous = signal.signal(signum, handler)
    yield
    signal.signal(signum, previous)


@contextlib.contextmanager
def install_handler(
    signals: Iterable[signal.Signals],
    handler: Callable[[int, Optional[types.FrameType]], Any],
):
    with contextlib.ExitStack() as stack:
        for signum in signals:
            stack.enter_context(install_handler_single(signum, handler))
        yield

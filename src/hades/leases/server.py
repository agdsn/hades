from __future__ import annotations
import array
import contextlib
import enum
import fcntl
import functools
import io
import logging
import mmap
import os
import signal
import socket
import socketserver
import struct
import sys
import threading
import typing

from collections.abc import (
    Iterable,
    Iterator,
)
from itertools import chain, repeat
from typing import Dict, Generator, List, Literal, Optional, Sequence, Tuple, TypeVar, TextIO

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from hades.bin.dhcp_script import Context, create_parser, dispatch_commands
from hades.common.signals import install_handler

logger = logging.getLogger(__name__)
SIZEOF_UINT = struct.calcsize("@I")
T = TypeVar('T')
Parser = Generator[
    int,  # what we yield
    Tuple[mmap.mmap, int],  # what we get sent
    T,  # what we return
]


class BaseParseError(Exception):
    def __init__(
        self,
        *args: typing.Any,
        element: Optional[str] = None,
        offset: Optional[int] = None,
    ) -> None:
        self.element = element
        self.offset = offset
        super().__init__(*args, element, offset)

    def _prefix(self) -> str:
        offset, element = self.offset, self.element
        return "".join([
            "" if offset is None else f"at offset {offset:d}: ",
            "" if element is None else f"while parsing {element}: ",
        ]).capitalize()

    def with_element(self, element: str) -> BaseParseError:  # ≥3.11: typing.Self
        self.element = element
        return self

    def with_offset(self, offset: int) -> BaseParseError:  # ≥3.11: typing.self
        self.offset = offset
        return self


class ParseError(BaseParseError):
    def __init__(
            self,
            message: str,
            *,
            element: Optional[str] = None,
            offset: Optional[int] = None,
    ) -> None:
        self.element = element
        self.offset = offset
        self.message = message
        super().__init__(message, element=element, offset=offset)

    def __str__(self) -> str:
        return self._prefix() + self.message


class UnexpectedEOFError(BaseParseError):
    def __init__(
            self,
            needed: int,
            available: int,
            *,
            element: Optional[str] = None,
            offset: Optional[int] = None,
    ) -> None:
        self.needed = needed
        self.available = available
        super().__init__(
            needed,
            available,
            element=element,
            offset=offset,
        )

    def __str__(self) -> str:
        return (
            f"{self._prefix()}"
            f"Unexpected end of file, expected at least {self.needed} more "
            f"byte(s), but only {self.available} byte(s) left."
        )


class BufferTooSmallError(BaseParseError):
    def __init__(
            self,
            needed: int,
            available: int,
            *,
            element: Optional[str] = None,
            offset: Optional[int] = None,
    ) -> None:
        self.needed = needed
        self.available = available
        super().__init__(
            needed,
            available,
            element=element,
            offset=offset,
        )

    def __str__(self) -> str:
        return (
            f"{self._prefix()}"
            f"Parser requires more data ({self.needed}) than can be buffered "
            f"({self.available})."
        )


class ProtocolError(Exception):
    pass


class Mode(enum.Enum):
    """
    Enum to distinguish I/O modes associate with corresponding Python mode
    strings and compatible POSIX file descriptor status flags.

    Conversion between POSIX file descriptor status flags and Python mode
    strings is difficult and sometimes impossible, e.g. there is no mode for
    `O_WRONLY` without `O_CREAT` or with neither `O_APPEND` nor `O_TRUNC`.
    Some flags (e.g. `O_CREAT`, `O_EXCL`, `O_TRUNC`) and mode strings (`"w"` and
    `"x"`) are actually only meaningful when opening a file initially. `"w"` is
    a particularly interesting case, as it always truncates the file if it
    exists. There is no way to open a file using mode strings only for writing
    (i.e. no appending or reading).

    Received file descriptors may be opened with different flags and access
    modes. TTY fds usually have access mode `O_RDWR` mode, the stdio io objects
    (e.g `sys.stdout`) are however always opened in read-only or write-only mode
    by Python. In fact, trying to open such a file descriptor with mode string
    `r+` (i.e. read-write mode) and using buffering causes :func:`os.fdopen` to
    refuse operation because the buffer is not seekable. See `issue 20074
    <https://bugs.python.org/issue20074#msg207012>` and the related discussion
    for some details on the CPython core developers' philosophy on this.
    """
    READ = "r", (os.O_RDONLY, os.O_RDWR), None
    WRITE = "w", (os.O_WRONLY, os.O_RDWR), False
    UPDATE = "r+", (os.O_RDWR,), False
    APPEND = "a", (os.O_RDONLY, os.O_RDWR), True
    READABLE_APPEND = "a+", (os.O_RDWR,), True

    def __init__(
        self, stdio_mode: str, access_mode: Tuple[int, ...], append: bool
    ) -> None:
        super().__init__()
        self.stdio_mode = stdio_mode
        self.access_mode = access_mode
        self.append = append


class LoopGuard(Iterator):
    """Throws a :class:`RuntimeError` after :paramref:`max` iterations.
    Useful to protect against infinite loops.

    Usage:
    >>> g = LoopGuard("outer_loop", max=100)
    >>> while True:
    ...     next(g)
    """

    def __init__(self, name: str, *, maximum: Optional[int] = 1000):
        self.name = name
        self.maximum = maximum
        self.counter = iter(range(maximum))

    def __next__(self) -> None:
        try:
            next(self.counter)
        except StopIteration:
            raise RuntimeError(
                f"LoopGuard {self.name} aborted execution after {self.maximum} iterations"
            ) from None


class Server(socketserver.UnixStreamServer):
    """
    Process :program:`dnsmasq` :option:`--dhcp-script` invocations.

    :program:`dnsmasq` can notify external tools about DHCP lease activity and
    even maintain a completely external lease database, if additionally
    :option:`--leasefile-ro` is specified. We use this mechanism to store the
    leases in the database.

    Starting a Python script that connects to a PostgreSQL database for DHCP
    lease activity of dnsmasq is too slow however:

    * The Python interpreter has some startup latency, but more importantly
      setuptools console scripts have a very long startup time (>1s) due to
      `this issue <https://github.com/pypa/setuptools/issues/510>`_.
    * PostgreSQL forks for every connection.

    To alleviate these issues we use a small and quick C client that passes its
    command-line arguments, environment variables and file descriptors over a
    UNIX socket to a long running Python server application that's permanently
    connected to the database. The server is single threaded and will only
    handle a single request at a time, because :program:`dnsmasq` itself is
    single threaded.

    The protocol is as follows:

    * We use a SOCK_STREAM AF_UNIX socket, so that the client knows on the
      socket level, when server has received all data and finished handling the
      request.
    * At first the client sends all data to server. The data may not exceed
      :py:code:`mmap.PAGESIZE - 1`. The content of the data is as follows:
        1. The first bytes are the number of arguments (:c:data:`argc`) as
           native type :c:type:`int`.
        2. This is followed by the contents of :c:data:`argv` as a series of
           zero terminated strings.
        3. After that the number of environment variables, that start with the
           prefix :envvar:`DNSMASQ_*` as native type :c:type:`int`.
        4. Followed by the actual environment variables as a series of zero
           terminated strings.
    * The three standard file descriptors stdin, stdout, and stderr of the
      script should be passed with data at some point in time via a
      :c:data:`SCM_RIGHTS` control message.
    * After all data has been sent, the client shuts down its write end of the
      connection and signals the server thereby, that it can begin processing
      the message.
    * The server will process the message and if necessary read additional data
      from the passed stdin file descriptor and write data to the passed stdout
      and stderr file descriptors.
    * After it has processed the message, the server sends a single byte status
      code between 0 and 127 and will close the connection. The script will
      exit with the status code.
    """
    max_packet_size = mmap.PAGESIZE - 1
    ancillary_buffer = socket.CMSG_LEN(struct.calcsize("@3i"))

    def __init__(
        self, sock: socket.socket, engine: Engine, dhcp_lease_table: Table
    ) -> None:
        self.parser = create_parser(standalone=False)
        self.engine = engine
        self.dhcp_lease_table = dhcp_lease_table
        server_address = sock.getsockname()
        super().__init__(
            server_address, self._request_handler, bind_and_activate=False,
        )
        self.socket = sock
        # Leave one byte extra for trailing zero byte
        # TODO: With Python 3.8 a memfd can be opened and mapped twice:
        # writable and readonly
        fd = os.memfd_create("buffer", os.MFD_CLOEXEC)
        os.ftruncate(fd, self.max_packet_size + 1)
        self.buffer = mmap.mmap(
            fd,
            self.max_packet_size + 1,
            mmap.MAP_PRIVATE,
            mmap.PROT_READ | mmap.PROT_WRITE,
        )

    def _request_handler(
        self,
        request: socket.socket,
        client_address: str,
        server: socketserver.BaseServer,
    ) -> None:
        assert self == server

        logger.debug("Received new request from %s", client_address)
        (stdin, stdout, stderr), args, env = self._receive(request)
        status = os.EX_SOFTWARE
        try:
            status = self._process(stdin, stdout, stderr, args, env)
        finally:
            stdout.flush()
            stderr.flush()
            request.send(status.to_bytes(1, sys.byteorder))

    def _receive(
        self, request: socket.socket
    ) -> Tuple[Tuple[TextIO, TextIO, TextIO], List[bytes], Dict[bytes, bytes]]:
        streams: List[TextIO] = []
        # Offset of the buffer relative to the input stream
        offset = 0
        # Number of filled bytes in the buffer
        available = 0
        # Initialize parser
        buffer = self.buffer
        buffer.seek(0, os.SEEK_SET)
        parser = self.parse_request()
        needed = next(parser)
        with contextlib.ExitStack() as stack:
            g = LoopGuard("_receive__needed")
            while needed:
                next(g)
                available = self.fill_buffer(
                    stack, streams, offset, available, needed, request
                )
                try:
                    parsed = 0
                    g2 = LoopGuard("_receive__available")
                    while parsed + needed <= available:
                        next(g2)
                        needed = parser.send((buffer, available))
                        parsed = buffer.tell()
                except StopIteration as e:
                    argv, environ = e.value
                    if buffer.tell() < available:
                        raise ProtocolError(
                            f"{available - buffer.tell()} byte(s) left over "
                            f"after parsing"
                        )
                    break
                except BaseParseError as e:
                    raise e.with_offset(offset + buffer.tell())

            if not streams:
                raise ProtocolError("No file descriptors received")
            if len(streams) != 3:
                raise ProtocolError(
                    "Expected to receive exactly 3 file descriptors"
                )
            stdin, stdout, stderr = streams
            # Clear the stack
            stack.pop_all()

        return (stdin, stdout, stderr), argv, environ

    def fill_buffer(self, stack, streams, offset, available, needed, sock):
        buffer = self.buffer
        g = LoopGuard("fill_buffer__needed")
        while available < needed:
            next(g)
            # Prepare buffer for refill
            parsed = buffer.tell()
            offset += parsed
            buffer.move(0, parsed, available - parsed)
            buffer.seek(0, os.SEEK_SET)
            available -= parsed
            if needed > self.max_packet_size:
                raise BufferTooSmallError(
                    needed,
                    self.max_packet_size,
                    offset=offset,
                )
            # Leave space for a trailing zero byte
            size, ancdata, msg_flags, _ = sock.recvmsg_into(
                (memoryview(buffer)[available:-1],),
                self.ancillary_buffer,
                socket.MSG_CMSG_CLOEXEC,
            )

            if not ancdata and not size:
                raise UnexpectedEOFError(
                    needed, available, offset=offset + available
                )

            available += size
            # Ensure that a trailing zero byte exists
            buffer[available] = 0

            new_streams = self.parse_ancillary_data(
                ancdata, (Mode.READ, Mode.WRITE, Mode.WRITE)
            )
            for stream in new_streams:
                stack.enter_context(stream)
            streams.extend(new_streams)

            if msg_flags & socket.MSG_CTRUNC:
                raise ProtocolError("Truncated ancillary data")

        return available

    @staticmethod
    def parse_ancillary_data(
        ancdata: Iterable[Tuple[int, int, bytes]],
        requested_modes: Sequence[Mode],
    ) -> List[TextIO]:
        """
        Open streams for file descriptors received via :func:`socket.recvmsg`
        ancillary data.

        :param ancdata:
        :param requested_modes: a sequence of modes in which the fds should be opened
        :return:
        """
        fds = array.array("i")
        streams: List[TextIO] = []
        with contextlib.ExitStack() as stack:
            truncated = False
            for cmsg_level, cmsg_type, cmsg_data in ancdata:
                if (
                        cmsg_level == socket.SOL_SOCKET
                        and cmsg_type == socket.SCM_RIGHTS
                ):
                    end = len(cmsg_data) - (len(cmsg_data) % fds.itemsize)
                    truncated |= end != len(cmsg_data)
                    fds.frombytes(cmsg_data[:end])
                else:
                    logger.warning(
                        "Received unexpected control message: level=%d type=%d",
                        cmsg_level, cmsg_type,
                    )
            # Ensure that file descriptors get closed on error
            for fd in fds:
                stack.callback(_try_close, fd)
            if truncated:
                raise ProtocolError(
                    "Received truncated file descriptor. "
                    "SCM_RIGHTS control message data must be an multiple of "
                    f"sizeof(int) = {fds.itemsize}"
                )

            requested_mode: Mode
            for num, (fd, requested_mode) in enumerate(
                zip_left_none(fds, requested_modes)
            ):
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                accmode = flags & os.O_ACCMODE
                appendable = flags & os.O_APPEND == os.O_APPEND

                if requested_mode is None:
                    requested_mode = (
                        Mode.READ if accmode != os.O_WRONLY else Mode.WRITE
                    )

                if accmode not in requested_mode.access_mode:
                    raise ProtocolError(
                        f"File descriptor at index {num} O_ACCMODE bits "
                        f"{accmode:02x} are not compatible with requested mode "
                        f"{requested_mode.name}."
                    )

                if requested_mode.append is True and not appendable:
                    try:
                        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_APPEND)
                    except OSError as e:
                        raise ProtocolError(
                            f"File descriptor at index {num} does not support "
                            f"O_APPEND."
                        ) from e

                if requested_mode.append is False and appendable:
                    try:
                        fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_APPEND)
                    except OSError as e:
                        raise ProtocolError(
                            f"File descriptor at index {num} does not support "
                            f"disabling O_APPEND."
                        ) from e

                # noinspection PyTypeChecker
                stdio_mode = requested_mode.stdio_mode
                try:
                    stream: TextIO = typing.cast(TextIO, os.fdopen(fd, stdio_mode, closefd=True))
                except io.UnsupportedOperation as e:
                    raise RuntimeError(
                        f"Unable to create IO object for fd at index {num} "
                        f"with mode {stdio_mode!r})"
                    ) from e
                streams.append(stream)
            stack.pop_all()

        return streams

    @staticmethod
    def parse_integer(
        length: int,
        element: str = "integer",
        byteorder: Literal["little", "big"] = sys.byteorder,
        signed: bool = False,
    ) -> Parser[int]:
        """Try to parse a C int"""
        try:
            data, size = yield length
        except BaseParseError as e:
            raise e.with_element(element)
        value = int.from_bytes(
            data.read(length), byteorder=byteorder, signed=signed
        )
        return value

    @staticmethod
    def parse_string(element: str = "string") -> Parser[bytes]:
        """Try to parse a zero-terminated C string"""
        need = 1
        g = LoopGuard("parse_string")
        while True:
            next(g)
            try:
                data, size = yield need
            except BaseParseError as e:
                raise e.with_element(element)
            # This is safe, because we ensure that underlying buffer is always
            # zero-terminated
            start = data.tell()
            end = data.find(b'\x00', start, size)
            if end != -1:
                string = data[start:end]
                data.seek(end + 1, os.SEEK_SET)
                return string
            else:
                need = size - start + 1

    @classmethod
    def parse_request(cls) -> Parser[Tuple[List[bytes], Dict[bytes, bytes]]]:
        # Parse number of arguments
        argc = yield from cls.parse_integer(SIZEOF_UINT, "argc")

        # Parse arguments
        argv = []
        for i in range(argc):
            arg = yield from cls.parse_string(f"argv[{i:d}]")
            argv.append(arg)

        # Parse number of environment variables
        envc = yield from cls.parse_integer(SIZEOF_UINT, "envc")

        # Parse environment variables
        environ = {}
        for i in range(envc):
            element = f"environ[{i:d}]"
            env = yield from cls.parse_string(element)
            name, sep, value = env.partition(b'=')
            if not sep:
                raise ParseError(
                    "No equal sign in environment variable: " + repr(name),
                    element=element,
                )
            environ[name] = value
        return argv, environ

    def _handle_shutdown_signal(self, signo: int, _frame: typing.Any) -> None:
        logger.critical("Received signal %d. Shutting down.", signo)
        # shutdown blocks until the server is stopped, therefore we must use a
        # separate thread, otherwise there will be deadlock
        threading.Thread(name='shutdown', target=self.shutdown).start()

    def serve_forever(self, poll_interval: float = 0.5):
        logger.info("Starting server loop")
        with install_handler(
            (signal.SIGHUP, signal.SIGINT, signal.SIGTERM),
            self._handle_shutdown_signal
        ):
            super().serve_forever(poll_interval)

    def _process(
            self,
            stdin: TextIO, stdout: TextIO, stderr: TextIO,
            args: Sequence[bytes], env: Dict[bytes, bytes]
    ) -> int:
        decoded_args = [decode(a) for a in args]
        parsed_args = self.parser.parse_args(decoded_args[1:])
        return dispatch_commands(
            args=parsed_args,
            context=Context(
                stdin=stdin, stdout=stdout, stderr=stderr,
                environ={decode(k): decode(v) for k, v in env.items()},
                environb=env,
                dhcp_lease_table=self.dhcp_lease_table,
            ),
            engine=self.engine,
        )


decode = functools.partial(
    bytes.decode,
    encoding=sys.getfilesystemencoding(),
    errors="surrogateescape",
)
"""Decode bytes like done in `os._createenviron`"""


def _try_close(fd):
    try:
        os.close(fd)
    except OSError as e:
        logger.error("Problem closing file descriptor", exc_info=e)


S = typing.TypeVar("S")


def zip_left(
    left: typing.Iterable[S], right: typing.Iterable[T], rfill: T
) -> typing.Iterable[typing.Tuple[S, T]]:
    return zip(left, chain(right, repeat(rfill)))


def zip_left_none(
    left: typing.Iterable[S], right: typing.Iterable[T]
) -> typing.Iterable[typing.Tuple[S, typing.Optional[T]]]:
    return zip_left(left, right, rfill=None)

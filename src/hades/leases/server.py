import array
import contextlib
import fcntl
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

from collections.abc import Container
from itertools import chain, repeat
from typing import Dict, Generator, List, Optional, Sequence, Tuple, TypeVar, TextIO

from hades.bin.dhcp_script import Context, create_parser, dispatch_commands
from hades.common.signals import install_handler

logger = logging.getLogger(__name__)
SIZEOF_INT = struct.calcsize("@i")
T = TypeVar('T')
Parser = Generator[int, Tuple[mmap.mmap, int], T]


class BaseParseError(Exception):
    def __init__(
            self,
            *args,
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

    def with_element(self, element: str):
        self.element = element
        return self

    def with_offset(self, offset: int):
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

    def __init__(self, sock, engine):
        self.parser = create_parser(standalone=False)
        self.engine = engine
        server_address = sock.getsockname()
        super().__init__(
            server_address, self._request_handler, bind_and_activate=False,
        )
        self.socket = sock
        # Leave one byte extra for trailing zero byte
        # TODO: With Python 3.8 a memfd can be opened and mapped twice:
        # writable and readonly
        fd = os.memfd_create(b"buffer", os.MFD_CLOEXEC)
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
            client_address,
            server: socketserver.BaseServer,
    ):
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
            self,
            request: socket.socket,
    ) -> Tuple[Tuple[TextIO, TextIO, TextIO], List[bytes], Dict[bytes, bytes]]:
        streams: List[TextIO] = []
        # Offset of the buffer relative to the input stream
        offset = 0
        # Number of filled bytes in the buffer
        available = 0
        # Initialize parser
        buffer = self.buffer
        buffer.seek(0, os.SEEK_SET)
        parser = self.parse_request(buffer, 0)
        needed = next(parser)
        with contextlib.ExitStack() as stack:
            while needed:
                # Prepare buffer for refill
                parsed = buffer.tell()
                offset += parsed
                buffer.move(0, parsed, available - parsed)
                buffer.seek(0, os.SEEK_SET)
                available -= parsed
                if needed > self.max_packet_size:
                    parser.throw(BufferTooSmallError(
                        needed,
                        self.max_packet_size,
                        offset=offset,
                    ))
                # Leave space for a trailing zero byte
                size, ancdata, msg_flags, _ = request.recvmsg_into(
                    (memoryview(buffer)[available:-1],),
                    socket.CMSG_LEN(3 * SIZEOF_INT),
                    socket.MSG_CMSG_CLOEXEC,
                )
                available += size
                # Ensure that a trailing zero byte exists
                buffer[available] = 0

                streams.extend(
                    stack.enter_context(stream)
                    for stream in self.parse_ancillary_data(ancdata, ["r", "w", "w"])
                )

                if msg_flags & socket.MSG_CTRUNC:
                    raise ProtocolError("Truncated ancillary data")

                try:
                    needed = parser.send((buffer, available))
                except StopIteration as e:
                    _, _, (argv, environ) = e.value
                    if buffer.tell() < available:
                        raise ProtocolError(
                            f"{available - buffer.tell()} byte(s) left over "
                            f"after parsing"
                        )
                    needed = 0
                except BaseParseError as e:
                    raise e.with_offset(offset + buffer.tell())
                else:
                    # Remote end closed/shut down writing
                    if needed > 0 and size == 0:
                        # Raise an error in the parser to produce an error with
                        # proper message
                        parser.throw(UnexpectedEOFError(
                            needed,
                            available,
                            offset=offset + buffer.tell(),
                        ))

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

    @staticmethod
    def parse_ancillary_data(
        ancdata: Container[Tuple[int, int, bytes]],
        requested_fd_modes: Sequence[str],
    ) -> List[TextIO]:
        """
        Open streams for file descriptors received via :func:`socket.recvmsg`
        ancillary data.

        :param ancdata:
        :param requested_fd_modes: a sequence of modes in which the fds should be opened
        :return:
        """
        fds = array.array("i")
        streams = []
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

            # It's not possible to correctly map every POSIX file descriptor
            # flag combination to a C stdlib fopen mode, e.g. there is no mode
            # for O_WRONLY without O_CREAT or with neither O_APPEND nor O_TRUNC,
            # therefore we verify if the underlying file descriptor flags are
            # compatible with the requested mode.
            for num, (fd, requested_fd_mode) in enumerate(
                zip_left(fds, requested_fd_modes)
            ):
                accmode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
                if accmode == os.O_RDONLY:
                    mode = "r"
                elif accmode == os.O_WRONLY:
                    mode = "w"
                elif accmode == os.O_RDWR:
                    # the stdout/stderr buffers can possibly be in RW mode,
                    # however the buffer used by `sys.stdout` is usually opened in
                    # write-only mode by python.
                    # in fact, opening this in `r+` (i.e. read-write mode) and using buffering
                    # causes open() to refuse operation because the buffer is not seekable.
                    # See https://bugs.python.org/issue20074#msg207012 and the related discussion
                    # for some details on the core developers' philosophy on this.
                    mode = requested_fd_mode or "w"
                else:
                    raise ProtocolError(
                        f"Unknown O_ACCMODE {accmode} of fd at index {num}"
                    )

                if mode != requested_fd_mode:
                    raise ProtocolError(
                        f"File descriptor O_ACCMODE {accmode:02x} of fd at "
                        f"index {num} is not compatible with requested mode "
                        f"{requested_fd_mode!r}."
                    )

                # noinspection PyTypeChecker
                try:
                    stream: TextIO = os.fdopen(fd, mode, closefd=True)
                except io.UnsupportedOperation as e:
                    raise RuntimeError(
                        f"Unable to create IO object for fd at index {num} "
                        f"with {mode=})"
                    ) from e
                streams.append(stream)
            stack.pop_all()
            return streams

    @staticmethod
    def parse_int(
            data: mmap.mmap,
            size: int,
            element: str = "int",
    ) -> Parser[int]:
        """Try to parse a C int"""
        need = SIZEOF_INT
        if data.tell() + need > size:
            try:
                data, size = yield need
            except BaseParseError as e:
                raise e.with_element(element)
        value = struct.unpack("=i", data.read(need))[0]
        return data, size, value

    @staticmethod
    def parse_string(
            data: mmap.mmap,
            size: int,
            element: str = "string"
    ) -> Parser[str]:
        """Try to parse a zero-terminated C string"""
        need = 1
        while True:
            if data.tell() + need > size:
                try:
                    data, size = yield need
                except BaseParseError as e:
                    raise e.with_element(element)
            # This is safe, because we ensure that underlying buffer is always
            # zero-terminated
            start = data.tell()
            end = data.find(b'\x00', start, size)
            if end != -1:
                arg = data[start:end]
                data.seek(end + 1, os.SEEK_SET)
                return data, size, arg
            else:
                need = size - start + 1

    @classmethod
    def parse_request(
            cls,
            data: mmap.mmap,
            size: int,
    ) -> Parser[Tuple[List[bytes], Dict[bytes, bytes]]]:
        # Parse number of arguments
        element = "argc"
        data, size, argc = yield from cls.parse_int(data, size, element)
        if argc < 0:
            raise ParseError("Negative argc: " + str(argc), element=element)

        # Parse arguments
        argv = []
        for i in range(argc):
            element = f"argv[{i:d}]"
            data, size, arg = yield from cls.parse_string(data, size, element)
            argv.append(arg)

        # Parse number of environment variables
        element = "envc"
        data, size, envc = yield from cls.parse_int(data, size, element)
        if envc < 0:
            raise ParseError("Negative envc: " + str(envc), element=element)

        # Parse environment variables
        environ = {}
        for i in range(envc):
            element = f"environ[{i:d}]"
            data, size, env = yield from cls.parse_string(data, size, element)
            name, sep, value = env.partition(b'=')
            if not sep:
                raise ParseError(
                    "No equal sign in environment variable: " + repr(name),
                    element=element,
                )
            environ[name] = value
        return data, size, (argv, environ)

    def _handle_shutdown_signal(self, signo, _frame):
        logger.critical("Received signal %d. Shutting down.", signo)
        # shutdown blocks until the server is stopped, therefore we must use a
        # separate thread, otherwise there will be deadlock
        threading.Thread(name='shutdown', target=self.shutdown).start()

    def serve_forever(self, poll_interval=0.5):
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
            ),
            engine=self.engine,
        )


def decode(x: bytes) -> str:
    """Decode a string like done in `os._createenviron` (hard-coding utf-8)"""
    return x.decode("utf-8", errors="surrogateescape")


def _try_close(fd):
    try:
        os.close(fd)
    except OSError as e:
        logger.error("Problem closing file descriptor", exc_info=e)


def zip_left(left, right, rfill=None):
    return zip(left, chain(right, repeat(rfill)))

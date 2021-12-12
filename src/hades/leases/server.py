import array
import contextlib
import ctypes
import fcntl
import logging
import mmap
import os
import signal
import socket
import socketserver
import struct
import threading
from io import FileIO

from collections.abc import Container
from typing import Dict, Generator, List, Optional, Tuple, TypeVar

from hades.common.signals import install_handler

logger = logging.getLogger(__name__)
SIZEOF_INT = ctypes.sizeof(ctypes.c_int)
memfd_create = ctypes.cdll.LoadLibrary("libc.so.6").memfd_create
MFD_CLOEXEC = 1
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
            "" if offset is None else "at offset {}: ".format(offset),
            "" if element is None else "while parsing {}: ".format(element),
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
            "{}Unexpected end of file, expected at least {} more byte(s), "
            "but only {} byte(s) left."
            .format(self._prefix(), self.needed, self.available)
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
            "{}Parser requires more data ({}) than can be buffered ({})."
            .format(self._prefix(), self.needed, self.available)
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
        self.engine = engine
        server_address = sock.getsockname()
        super().__init__(
            server_address, self._request_handler, bind_and_activate=False,
        )
        self.socket = sock
        # Leave one byte extra for trailing zero byte
        # TODO: With Python 3.8 a memfd can be opened and mapped twice:
        # writable and readonly
        fd = memfd_create(b"buffer", MFD_CLOEXEC)
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
            status = self._process()
        finally:
            stdout.flush()
            stderr.flush()
            self._send(status)

    def _receive(
            self,
            request: socket.socket,
    ) -> Tuple[Tuple[FileIO, FileIO, FileIO], List[bytes], Dict[bytes, bytes]]:
        streams: List[FileIO] = []
        # Offset of the buffer relative to the input stream
        offset = 0
        # Number of filled bytes in the buffer
        available = 0
        # Initialize parser
        buffer = self.buffer
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
                    for stream in self.parse_ancillary_data(ancdata)
                )

                if msg_flags & socket.MSG_CTRUNC:
                    raise ProtocolError("Truncated ancillary data")

                try:
                    needed = parser.send((buffer, available))
                except StopIteration as e:
                    _, _, (argv, environ) = e.value
                    if buffer.tell() < available:
                        raise ProtocolError(
                            "{} byte(s) left over after parsing"
                            .format(available - buffer.tell())
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
            stdin = streams[0]
            if not stdin.mode.startswith('rb'):
                raise ProtocolError()
            stdout = streams[1]
            if not stdout.mode.startswith('wb'):
                raise ProtocolError()
            stderr = streams[2]
            if not stderr.mode.startswith('wb'):
                raise ProtocolError()
            # Clear the stack
            stack.pop_all()
            return (stdin, stdout, stderr), argv, environ

    @staticmethod
    def parse_ancillary_data(
            ancdata: Container[Tuple[int, int, bytes]],
    ) -> List[FileIO]:
        """
        Open streams for file descriptors received via :func:`socket.recvmsg`
        ancillary data.

        :param ancdata:
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
                stack.callback(os.close, fd)
            if truncated:
                raise ProtocolError(
                    "Received truncated file descriptor. "
                    "SCM_RIGHTS control message data must be an multiple of "
                    "sizeof(int) = {}".format(fds.itemsize)
                )
            for fd in fds:
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                if flags & os.O_ACCMODE == os.O_RDONLY:
                    mode = "rb"
                elif flags & os.O_ACCMODE == os.O_WRONLY:
                    mode = "wb"
                elif flags & os.O_ACCMODE == os.O_RDWR:
                    mode = "rb+"
                else:
                    os.close(fd)
                    continue
                # noinspection PyTypeChecker
                stream: FileIO = os.fdopen(fd, mode, buffering=0, closefd=True)
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
            element = "argv[{:d}]".format(i)
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
            element = "environ[{}]".format(i)
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
        logger.error("Received signal %d. Shutting down.", signo)
        threading.Thread(name='shutdown', target=self.shutdown).start()

    def serve_forever(self, poll_interval=0.5):
        logger.info("Starting server loop")
        with install_handler(
            (signal.SIGHUP, signal.SIGINT, signal.SIGTERM),
            self._handle_shutdown_signal
        ):
            super().serve_forever(poll_interval)

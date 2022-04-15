import abc
import asyncio
import collections
import contextlib
import fcntl
import functools
import inspect
import io
import mmap
import operator
import os
import pathlib
import random
import signal
import socket
import stat
import struct
import subprocess
import tempfile
import termios
import time
import types
import typing
import warnings

from typing import Any, BinaryIO, Callable, Dict, Generator, List, Optional, Set, Tuple

import pytest
import trio
from setuptools import Distribution

from hades import constants
from hades.leases.server import Mode, Server


# Available since CPython 3.10
F_GETPIPE_SZ = getattr(fcntl, "F_GETPIPE_SZ", 1032)
AncillaryData = List[Tuple[int, int, bytes]]
RECVMSG = Tuple[bytes, AncillaryData, int]
Result = Tuple[
    int,
    bytes,
    bytes,
    Optional[List[RECVMSG]],
    Optional[bytes],
]
T = typing.TypeVar('T')
SIZEOF_INT = struct.calcsize("@i")
ucred = struct.Struct("iII")
TIMEOUT = 1.0
RECVMSG_FLAGS = socket.MSG_CMSG_CLOEXEC


@pytest.fixture(scope="session")
def socket_path() -> bytes:
    return os.fsencode(tempfile.mktemp(prefix="hades-", suffix=".sock"))


def read_int_sysctl(variable: str) -> int:
    with (pathlib.PosixPath("/proc/sys") / variable).open("rb", 0) as f:
        return int(f.read())


@pytest.fixture(scope="session")
def optmem_max() -> int:
    return read_int_sysctl("net/core/optmem_max")


@pytest.fixture(scope="session")
def wmem_default() -> int:
    return read_int_sysctl("net/core/wmem_default")


@pytest.fixture(scope="session")
def uid():
    return os.getuid()


@pytest.fixture(scope="session")
def gid():
    return os.getgid()


@pytest.fixture(scope="class")
def server(socket_path) -> socket.socket:
    with contextlib.ExitStack() as stack:
        type_ = socket.SOCK_STREAM | socket.SOCK_NONBLOCK | socket.SOCK_CLOEXEC
        sock = stack.enter_context(socket.socket(socket.AF_UNIX, type_))
        sock.bind(socket_path)
        stack.callback(os.unlink, socket_path)
        sock.listen()
        yield sock


def test_short_write_possible(wmem_default):
    """On Linux only the sender can influence the size of a Unix stream socket
    buffer."""
    got = os.sysconf("SC_ARG_MAX")
    expected = wmem_default + mmap.PAGESIZE
    assert got > expected, "Cannot test short writes"


@contextlib.contextmanager
def chdir(directory):
    prev_cwd = os.getcwd()
    os.chdir(directory)
    try:
        yield directory
    finally:
        os.chdir(prev_cwd)


@pytest.fixture(scope="session")
def executable(request) -> pathlib.PosixPath:
    """Let setuptools compute the path to the built executable"""
    with chdir(request.config.rootdir) as root_dir:
        command = "build"
        distribution = Distribution({
            "script_name": __file__,
            "script_args": [command],
        })
        distribution.parse_config_files()
        distribution.parse_command_line()
        command = distribution.get_command_obj(command)
        command.ensure_finalized()
        return (
            pathlib.PosixPath(root_dir).absolute()
            / command.build_platlib
            / "hades-dhcp-script"
        )


def test_executable_exists(executable: pathlib.PosixPath):
    assert executable.exists()


class ChildStopped(Exception):
    pass


class TimeoutExceeded(Exception):
    pass


@contextlib.contextmanager
def pipe():
    r, w = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    r = os.fdopen(r, "r", closefd=True)
    w = os.fdopen(w, "w", closefd=True)
    with r, w:
        yield r, w


def drain_pipe(stream: io.TextIOWrapper, buffer: typing.BinaryIO) -> Optional[int]:
    chunk = stream.buffer.read()
    if chunk is not None:
        buffer.write(chunk)
        return len(chunk)
    else:
        return None


async def read_pipe(stream: trio.abc.ReceiveStream, buffer: io.BytesIO):
    async for chunk in stream:
        buffer.write(chunk)


async def receive_messages(
        client: trio.SocketStream,
        wmem_default: int,
        optmem_max: int,
        messages: List[RECVMSG],
):
    while (r := await client.socket.recvmsg(
            wmem_default,
            optmem_max,
            RECVMSG_FLAGS,
    ))[0]:
        messages.append(r[:3])


async def send_reply(client: trio.SocketStream, reply: bytes) -> bytes:
    reply = memoryview(reply)
    sent_total = 0

    try:
        while (
                sent_total < len(reply)
                and (sent := await client.socket.send(reply[sent_total:]))
        ):
            sent_total += sent
    except BrokenPipeError:
        pass

    return reply[:sent_total].tobytes()


async def track_process(process: trio.Process):
    await process.wait()
    raise ChildStopped()


async def run_with_trio(
        executable: pathlib.PosixPath,
        argv: List[bytes],
        environ: Dict[bytes, bytes],
        stdin: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        stdout: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        stderr: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        server: socket.socket,
        reply: bytes,
        wmem_default: int,
        optmem_max: int,
        uid: int,
        gid: int,
) -> Result:
    stdout_content = io.BytesIO()
    stderr_content = io.BytesIO()
    messages = None
    sent = None
    with trio.move_on_after(TIMEOUT):
        process = await trio.open_process(
            argv,
            executable=executable,
            env=environ,
            bufsize=0,
            text=False,
            encoding=None,
            stdin=os.dup(stdin[0].fileno()),
            stdout=os.dup(stdout[1].fileno()),
            stderr=os.dup(stderr[1].fileno()),
        )
        try:
            async with trio.open_nursery() as nursery:
                nursery: trio.Nursery = nursery
                # Read stdout/stderr in the background
                nursery.start_soon(track_process, process)
                nursery.start_soon(read_pipe, trio.lowlevel.FdStream(os.dup(stdout[0].fileno())), stdout_content)
                nursery.start_soon(read_pipe, trio.lowlevel.FdStream(os.dup(stderr[0].fileno())), stderr_content)
                server = trio.socket.from_stdlib_socket(server)
                client, _ = await server.accept()
                client = trio.SocketStream(client)
                credentials = ucred.unpack(client.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, ucred.size,
                ))
                assert (process.pid, uid, gid) == credentials
                messages = []
                await receive_messages(client, wmem_default, optmem_max, messages)
                sent = await send_reply(client, reply)
                await client.send_eof()
        except ChildStopped:
            pass
        else:
            process.kill()
        drain_pipe(stdout[0], stdout_content)
        drain_pipe(stderr[0], stderr_content)

    return process.returncode, stdout_content.getvalue(), stderr_content.getvalue(), messages, sent


class BaseRun(abc.ABC):
    RECVMSG_FLAGS = socket.MSG_CMSG_CLOEXEC
    TIMEOUT = 5.0

    @pytest.fixture(scope="class")
    def environ(self, server: socket.socket) -> Dict[bytes, bytes]:
        path = os.fsencode(server.getsockname())
        return collections.OrderedDict((
            (b"HADES_DHCP_SCRIPT_SOCKET", path),
        ))

    @pytest.fixture(scope="class")
    def stdin(self) -> Tuple[io.TextIOWrapper, io.TextIOWrapper]:
        with pipe() as p:
            yield p

    @pytest.fixture(scope="class")
    def stdout(self) -> Tuple[io.TextIOWrapper, io.TextIOWrapper]:
        with pipe() as p:
            yield p

    @pytest.fixture(scope="class")
    def stderr(self) -> Tuple[io.TextIOWrapper, io.TextIOWrapper]:
        with pipe() as p:
            yield p

    @pytest.fixture(scope="class")
    def result(
            self,
            executable: pathlib.PosixPath,
            argv: List[bytes],
            environ: Dict[bytes, bytes],
            stdin: Tuple[io.TextIOWrapper, io.TextIOWrapper],
            stdout: Tuple[io.TextIOWrapper, io.TextIOWrapper],
            stderr: Tuple[io.TextIOWrapper, io.TextIOWrapper],
            server: socket.socket,
            reply: bytes,
            wmem_default: int,
            optmem_max: int,
            uid: int,
            gid: int,
    ) -> Result:

        return trio.run(
            run_with_trio,
            executable,
            argv,
            environ,
            stdin,
            stdout,
            stderr,
            server,
            reply,
            wmem_default,
            optmem_max,
            uid,
            gid,
        )

    @pytest.fixture(scope="class")
    def status(self, result: Result) -> int:
        return result[0]

    @pytest.fixture(scope="class")
    def stdout_content(self, result: Result) -> bytes:
        return result[1]

    @pytest.fixture(scope="class")
    def stderr_content(self, result: Result) -> bytes:
        return result[2]

    @pytest.fixture(scope="class")
    def messages(self, result: Result) -> Optional[List[RECVMSG]]:
        return result[3]

    @pytest.fixture(scope="class")
    def sent(self, result: Result) -> Optional[bytes]:
        return result[4]

    @property
    @abc.abstractmethod
    def expected_status(self) -> int:
        pass

    @pytest.fixture(scope="class")
    def reply(self) -> bytes:
        return struct.pack("b", self.expected_status)

    def test_status(self, status: int):
        assert status == self.expected_status

    @property
    @abc.abstractmethod
    def expected_stdout(self) -> bytes:
        pass

    def test_stdout_content(self, stdout_content: bytes):
        assert stdout_content == self.expected_stdout

    @property
    @abc.abstractmethod
    def expected_stderr(self) -> bytes:
        pass

    def test_stderr_content(self, stderr_content: bytes):
        assert stderr_content == self.expected_stderr


class SuccessfulRun(BaseRun, abc.ABC):
    @property
    def expected_status(self):
        return os.EX_OK


class NoStdoutOutputRun(BaseRun, abc.ABC):
    @property
    def expected_stdout(self) -> bytes:
        return b""


class PrematureExitRun(NoStdoutOutputRun, abc.ABC):
    @property
    def expected_stderr(self) -> bytes:
        return inspect.cleandoc(
            f"""
            hades-dhcp-script ARGS...
            
            Sends its command-line arguments, environment variables starting
            with DNSMASQ_ and the stdin/stdout file descriptors to the UNIX
            socket set via the HADES_DHCP_SCRIPT_SOCKET environment
            variable (defaults to {constants.AUTH_DHCP_SCRIPT_SOCKET}).

            See the -6, --dhcp-script options of dnsmasq for details.
            """
        ).encode("ascii")

    def test_messages(self, messages: Optional[List[RECVMSG]]):
        assert messages is None

    def test_sent(self, sent: Optional[bytes]):
        assert sent is None


class TestUsageExit(PrematureExitRun):
    @property
    def expected_status(self) -> int:
        return os.EX_USAGE

    @pytest.fixture(scope="session")
    def argv(self, executable: pathlib.PosixPath) -> List[bytes]:
        return [bytes(executable)]


class TestHelpExit(PrematureExitRun, SuccessfulRun):
    @pytest.fixture(
        scope="session",
        params=[[b"-h"], [b"--help"], [b"help"]]
    )
    def argv(self, request, executable: pathlib.PosixPath) -> List[bytes]:
        return [bytes(executable)] + request.param


class ConnectedRun(BaseRun, abc.ABC):
    @pytest.fixture(scope="class")
    def messages(self, result: Result) -> List[RECVMSG]:
        messages = result[3]
        if messages is None:
            pytest.fail("No messages")
        return messages

    @pytest.fixture(scope="class")
    def file_descriptors(
        self,
        messages: List[RECVMSG],
    ) -> Generator[List[io.TextIOWrapper], None, None]:
        streams = []
        with contextlib.ExitStack() as stack:
            for _, ancdata, _ in messages:
                streams.extend(
                    stack.enter_context(stream)
                    for stream in Server.parse_ancillary_data(
                        ancdata, (Mode.READ, Mode.WRITE, Mode.WRITE)
                    )
                )
            # Make received file descriptors non-blocking
            for stream in streams:
                os.set_blocking(stream.fileno(), False)
            yield streams

    @pytest.fixture(scope="class")
    def passed_stdin(self, file_descriptors: List[io.TextIOWrapper]):
        if len(file_descriptors) != 3:
            pytest.fail("Wrong number of file descriptors")
        return file_descriptors[0]

    @pytest.fixture(scope="class")
    def passed_stdout(self, file_descriptors: List[io.TextIOWrapper]):
        if len(file_descriptors) != 3:
            pytest.fail("Wrong number of file descriptors")
        return file_descriptors[1]

    @pytest.fixture(scope="class")
    def passed_stderr(self, file_descriptors: List[io.TextIOWrapper]):
        if len(file_descriptors) != 3:
            pytest.fail("Wrong number of file descriptors")
        return file_descriptors[2]

    def test_sent(self, sent: Optional[bytes], reply: bytes):
        assert sent == reply

    def test_flags(self, messages: Optional[List[RECVMSG]]):
        got = [flags for _, _, flags in messages]
        expected = [self.RECVMSG_FLAGS for _, _, _ in messages]
        assert got == expected

    def test_ancillary_data(self, messages: Optional[List[RECVMSG]]):
        expected = [
            (
                socket.SOL_SOCKET,
                socket.SCM_RIGHTS,
                len(cmsg_data) - len(cmsg_data) % SIZEOF_INT,
            )
            for _, ancdata, _ in messages
            for _, _, cmsg_data in ancdata
        ]
        got = [
            (cmsg_level, cmsg_type, len(cmsg_data))
            for _, ancdata, _ in messages
            for cmsg_level, cmsg_type, cmsg_data in ancdata
        ]
        assert got == expected

    @pytest.mark.xfail(raises=BlockingIOError)
    def test_file_descriptor_count(
            self,
            file_descriptors: List[BinaryIO],
    ):
        assert len(file_descriptors) == 3

    @staticmethod
    def assert_file(our_file: io.TextIOWrapper, passed_file: io.TextIOWrapper):
        our_readable = our_file.readable()
        got_mode = passed_file.mode
        our_stat = os.fstat(our_file.fileno())
        passed_stat = os.fstat(passed_file.fileno())
        is_fifo = stat.S_ISFIFO(passed_stat.st_mode)
        expected_mode = "w" if our_readable else "r"
        reader = our_file if our_readable else passed_file
        writer = passed_file if our_readable else our_file
        # Verify that we have a pipe with its two ends
        if is_fifo and our_stat == passed_stat:
            pipe_size = fcntl.fcntl(writer.fileno(), F_GETPIPE_SZ)
            # Check for pending bytes in the pipe
            pending_bytes = bytearray(SIZEOF_INT)
            fcntl.ioctl(reader.fileno(), termios.FIONREAD, pending_bytes)
            pending_bytes = struct.unpack_from("=i", pending_bytes)[0]
            test_size = min(mmap.PAGESIZE, pipe_size - pending_bytes)
            expected_bytes = random.randbytes(test_size)
            writer.buffer.write(expected_bytes)
            writer.buffer.flush()
            got_bytes = reader.buffer.read(pipe_size)
        else:
            expected_bytes = None
            got_bytes = None
        assert (
            got_mode, is_fifo, passed_stat, got_bytes
        ) == (
            expected_mode, True, our_stat, expected_bytes
        )

    @pytest.mark.xfail(raises=BlockingIOError)
    def test_passed_stdin(
        self,
        stdin: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        passed_stdin: io.TextIOWrapper,
    ):
        self.assert_file(stdin[1], passed_stdin)

    @pytest.mark.xfail(raises=BlockingIOError)
    def test_passed_stdout(
        self,
        stdout: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        passed_stdout: io.TextIOWrapper,
    ):
        self.assert_file(stdout[0], passed_stdout)

    @pytest.mark.xfail(raises=BlockingIOError)
    def test_passed_stderr(
        self,
        stderr: Tuple[io.TextIOWrapper, io.TextIOWrapper],
        passed_stderr: io.TextIOWrapper,
    ):
        self.assert_file(stderr[0], passed_stderr)

    def test_message(
            self,
            argv: List[bytes],
            environ: Dict[bytes, bytes],
            messages: Optional[List[RECVMSG]],
    ):
        got = b"".join(map(operator.itemgetter(0), messages))
        expected = b"".join([
            struct.pack("@i", len(argv)),
        ] + [
            arg + b"\x00" for arg in argv
        ] + [
            struct.pack("@i", len(environ)),
        ] + [
            b"%b=%b\x00" % i for i in environ.items()
        ])
        assert got == expected


class TestSuccess(ConnectedRun, SuccessfulRun, NoStdoutOutputRun):
    @property
    def expected_stderr(self) -> bytes:
        return b""

    @pytest.fixture(scope="session")
    def argv(
        self,
        executable: pathlib.PosixPath,
        wmem_default: int,
    ) -> List[bytes]:
        random_args = random.randbytes(2 * wmem_default).split(b"\x00")
        return [
            bytes(executable),
            b"add",
        ] + random_args

    @pytest.fixture(scope="class")
    def environ(self, server: socket.socket) -> Dict[bytes, bytes]:
        path = os.fsencode(server.getsockname())
        return collections.OrderedDict((
            (b"NON_DNSMASQ_PREFIX_ENV", b"1"),
            (b"DNSMASQ_PREFIX_ENV", b"2"),
            (b"DNSMASQ_PREFIX_WITH_WHITESPACE", b" \twith\t whitespace\t "),
            (b"DNSMASQ_CHARACTERS", bytes(range(0x01, 0x100))),
            (b"HADES_DHCP_SCRIPT_SOCKET", path),
        ))


class TestExitStatus(ConnectedRun, NoStdoutOutputRun):
    @property
    def expected_stderr(self) -> bytes:
        return b""

    @pytest.fixture(scope="session")
    def argv(self, executable: pathlib.PosixPath) -> List[bytes]:
        return [
            bytes(executable),
            b"test"
        ]

    @property
    def expected_status(self) -> int:
        return 5

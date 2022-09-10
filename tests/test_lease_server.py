import array
import contextlib
import io
import logging
import mmap
import os
import socket
import struct
from io import FileIO

from typing import Callable, Dict, Generator, List, Optional, Sequence, Tuple, TypeVar

import pytest
from _pytest.logging import LogCaptureFixture

from hades.leases.server import (
    BufferTooSmallError, BaseParseError, Mode, ParseError, Parser, Server, UnexpectedEOFError, zip_left,
)

T = TypeVar('T')
ParserFactory = Callable[[mmap.mmap, int], Parser[T]]
Driver = Callable[[mmap.mmap, int, ParserFactory], T]


@pytest.fixture(
    params=(
        [Mode.READ],
        [Mode.WRITE],
        [Mode.UPDATE],
        [Mode.READ, Mode.WRITE, Mode.UPDATE],
    ),
    scope="session"
)
def modes(request) -> Sequence[Mode]:
    return request.param


@pytest.fixture
def files(modes) -> List[io.TextIOWrapper]:
    with contextlib.ExitStack() as stack:
        # Must use closefd=False, because parse_ancillary_data will return
        # streams with closefd=True.
        # noinspection PyTypeChecker
        yield [
            stack.enter_context(os.fdopen(
                os.open(os.devnull, flags=mode.access_mode[0]),
                mode=mode.stdio_mode,
                closefd=False,
            ))
            for mode in modes
        ]


def test_parse_ancillary_data(modes: Sequence[Mode], files: List[FileIO]):
    with contextlib.ExitStack() as stack:
        for file in files:
            stack.callback(os.close, file.fileno())
        data = [(
            socket.SOL_SOCKET,
            socket.SCM_RIGHTS,
            array.array("i", [f.fileno() for f in files]).tobytes(),
        )]
        streams = Server.parse_ancillary_data(data, modes)
        stack.pop_all()
    assert [
        (stream.fileno(), stream.mode) for stream in streams
    ] == [
        (file.fileno(), file.mode) for file in files
    ]


def test_parse_ancillary_data_unknown(caplog: LogCaptureFixture):
    data = [(
        socket.SOL_SOCKET,
        socket.SCM_CREDENTIALS,
        struct.pack("@iII", 1, 0, 0),
    )]
    streams = Server.parse_ancillary_data(data, ())
    assert len(streams) == 0
    assert caplog.record_tuples == [(
        Server.__module__,
        logging.WARNING,
        "Received unexpected control message: level=%d type=%d" % (
            socket.SOL_SOCKET, socket.SCM_CREDENTIALS,
        ),
    )]


def create_buffer(size: int = mmap.PAGESIZE):
    return mmap.mmap(
        -1,
        size,
        mmap.MAP_PRIVATE,
        mmap.PROT_READ | mmap.PROT_WRITE,
    )


@pytest.fixture(
    params=[0, 255],
    ids=lambda offset: 'offset={:d}'.format(offset),
)
def buffer(request) -> Generator[mmap.mmap, None, None]:
    with create_buffer() as b:
        b.seek(request.param, os.SEEK_SET)
        yield b


def drive_at_once(buffer: mmap.mmap, size: int, parser: ParserFactory[T]) -> T:
    """Pass all data to a parser"""
    generator = parser(buffer, size)
    with contextlib.closing(generator):
        try:
            needed = next(generator)
        except StopIteration as e:
            assert id(e.value[0]) == id(buffer)
            assert e.value[1] == size
            return e.value[2]
        except BaseParseError as e:
            raise e.with_offset(buffer.tell())
        else:
            offset = buffer.tell()
            if needed > len(buffer):
                generator.throw(BufferTooSmallError(needed, len(buffer), offset=offset))
            else:
                generator.throw(UnexpectedEOFError(needed, size - offset, offset=offset))


def drive_minimal(buffer: mmap.mmap, size: int, parser: ParserFactory[T]) -> T:
    """Pass only the minimum number of requested bytes to a parser"""
    end = size
    size = buffer.tell()
    generator = parser(buffer, size)
    needed = next(generator)

    with contextlib.closing(generator):
        while buffer.tell() + needed <= end:
            try:
                size = buffer.tell() + needed
                needed = generator.send((buffer, size))
            except StopIteration as e:
                assert id(e.value[0]) == id(buffer)
                assert e.value[1] == size
                return e.value[2]
            except BaseParseError as e:
                raise e.with_offset(buffer.tell())
        offset = buffer.tell()
        if needed > len(buffer):
            generator.throw(BufferTooSmallError(needed, len(buffer), offset=offset))
        else:
            generator.throw(UnexpectedEOFError(needed, end - offset, offset=offset))


@pytest.fixture(scope='session', params=[drive_at_once, drive_minimal])
def driver(request) -> Driver[T]:
    return request.param


def fill_buffer(buffer: mmap.mmap, value: bytes) -> int:
    start = buffer.tell()
    buffer.write(value)
    size = buffer.tell()
    # Trailing zero byte
    buffer.write_byte(0)
    buffer.seek(start, os.SEEK_SET)
    return size


@pytest.mark.parametrize(
    "value", [0, 1, 2, 3, 4, -1],
)
def test_parse_valid_int(driver: Driver[int], buffer: mmap.mmap, value: int):
    size = fill_buffer(buffer, struct.pack("@i", value))

    parsed_value = driver(buffer, size, Server.parse_int)
    assert parsed_value == value
    assert buffer.tell() == size


def test_parse_int_eof(driver: Driver[int], buffer: mmap.mmap):
    offset = buffer.tell()
    serialized = struct.pack("@i", -1)
    end = len(serialized) // 2
    size = fill_buffer(buffer, serialized[:end])

    with pytest.raises(UnexpectedEOFError) as e:
        driver(buffer, size, Server.parse_int)
    assert e.value.element == "int"
    assert e.value.offset == offset


def test_parse_int_buffer_too_small(driver: Driver[int]):
    value = struct.pack("@i", -1)
    size = len(value) // 2
    with create_buffer(size) as buffer:
        buffer[:] = value[:size]
        with pytest.raises(BufferTooSmallError) as e:
            driver(buffer, size, Server.parse_int)
        assert e.value.element == "int"
        assert e.value.offset == 0


@pytest.mark.parametrize(
    "value",
    [b"test", b"", bytes(range(0x01, 0x100))],
    ids=("test", "empty string", "all bytes")
)
def test_parse_valid_string(
        driver: Driver[bytes],
        buffer: mmap.mmap,
        value: bytes,
):
    size = fill_buffer(buffer, value + b"\x00")

    parsed_value = driver(buffer, size, Server.parse_string)
    assert parsed_value == value
    assert buffer.tell() == size


def test_parse_string_eof(driver: Driver[bytes], buffer: mmap.mmap):
    offset = buffer.tell()
    size = fill_buffer(buffer, b"test")

    with pytest.raises(UnexpectedEOFError) as e:
        driver(buffer, size, Server.parse_string)
    assert e.value.element == "string"
    assert e.value.offset == offset


def test_parse_string_buffer_too_small(driver: Driver[bytes]):
    value = b"test"
    size = len(value)
    with create_buffer(size) as buffer:
        buffer[:] = value
        with pytest.raises(BufferTooSmallError) as e:
            driver(buffer, size, Server.parse_string)
        assert e.value.element == "string"
        assert e.value.offset == 0


def serialize_request(
        argv: List[bytes],
        environ: Dict[bytes, bytes],
        argc: Optional[int] = None,
        envc: Optional[int] = None,
) -> bytes:
    return b"".join([
        struct.pack("@i", len(argv) if argc is None else argc),
    ] + [
        arg + b"\x00" for arg in argv
    ] + [
        struct.pack("@i", len(environ) if envc is None else envc),
    ] + [
        k + b"=" + v + b"\x00" for k, v in environ.items()
    ])


@pytest.mark.parametrize(
    "argv,environ",
    [
        ([], {}),
        ([b"arg0", b"add"], {b"DNSMASQ_ENV": b"1"}),
    ],
)
def test_parse_valid_request(
        driver: Driver[Tuple[List[bytes], Dict[bytes, bytes]]],
        buffer: mmap.mmap,
        argv: List[bytes],
        environ: Dict[bytes, bytes],
):
    size = fill_buffer(buffer, serialize_request(argv, environ))
    got_argv, got_environ = driver(buffer, size, Server.parse_request)
    assert (argv, environ) == (got_argv, got_environ)


def test_parse_negative_argc(
        driver: Driver[Tuple[List[bytes], Dict[bytes, bytes]]],
        buffer: mmap.mmap,
):
    size = fill_buffer(buffer, serialize_request([], {}, -1))
    with pytest.raises(ParseError):
        driver(buffer, size, Server.parse_request)


def test_parse_overflow_argc(
        driver: Driver[Tuple[List[bytes], Dict[bytes, bytes]]],
        buffer: mmap.mmap,
):
    size = fill_buffer(buffer, serialize_request([], {}, 1, -1))
    with pytest.raises(UnexpectedEOFError) as e:
        driver(buffer, size, Server.parse_request)
    assert e.value.element == "argv[0]"


def test_parse_overflow_envc(
        driver: Driver[Tuple[List[bytes], Dict[bytes, bytes]]],
        buffer: mmap.mmap,
):
    size = fill_buffer(buffer, serialize_request([], {}, None, 1))
    with pytest.raises(UnexpectedEOFError) as e:
        driver(buffer, size, Server.parse_request)
    assert e.value.element == "environ[0]"


def test_zip_left():
    assert list(zip_left("abc", "a", rfill="X")) == [
        ("a", "a"),
        ("b", "X"),
        ("c", "X"),
    ]
    assert list(zip_left("abc", "abcde", rfill="X")) == [
        ("a", "a"),
        ("b", "b"),
        ("c", "c"),
    ]

import datetime
import enum
import secrets
import socket
from functools import partial
from itertools import chain
from typing import Optional

import netaddr
import pytest

from hades.deputy.dhcp import make_release_packet, send_dhcp_packet


uint8be = partial(int.to_bytes, length=1, byteorder='big', signed=False)
uint16be = partial(int.to_bytes, length=2, byteorder='big', signed=False)
uint32be = partial(int.to_bytes, length=4, byteorder='big', signed=False)


@pytest.fixture(
    scope='session',
    params=(netaddr.IPAddress('172.17.0.1'),),
    ids=lambda ip: f'server_ip={ip}',
)
def server_ip(request) -> netaddr.IPAddress:
    return request.param


@pytest.fixture(
    scope='session',
    params=(netaddr.IPAddress("192.168.0.1"),),
    ids=lambda ip: f'client_ip={ip}',
)
def client_ip(request) -> netaddr.IPAddress:
    return request.param


@pytest.fixture(
    scope='session',
    params=(netaddr.EUI("00:11:22:33:44:55"),),
    ids=lambda mac: f'client_mac={mac}',
)
def client_mac(request) -> netaddr.EUI:
    return request.param


@pytest.fixture(scope='session')
def time() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def duid_llt(mac: netaddr.EUI, time: datetime.datetime) -> bytes:
    start = datetime.datetime(
        2000, 1, 1, 0, 0, 0, 0, tzinfo=datetime.timezone.utc,
    )
    timestamp = (time - start).seconds & 0xffffffff
    return b'\x00\x01' + uint32be(timestamp) + mac.packed


def duid_en(mac: netaddr.EUI, _: datetime.datetime) -> bytes:
    # AG DSN Private Enterprise Number: 45084
    return uint32be(45084) + mac.packed


def duid_ll(mac: netaddr.EUI, _: datetime.datetime) -> bytes:
    return b'\x00\x01' + mac.packed


def duid_uuid(mac: netaddr.EUI, time: datetime.datetime) -> bytes:
    """Generate a RFC 4122 version 1 UUID"""
    start = datetime.datetime(
        1582, 10, 15, 0, 0, 0, 0,
        tzinfo=datetime.timezone.utc,
    )
    clock_seq = 0
    timestamp = round((time - start).total_seconds() * 10e6)
    time_low = timestamp & 0xFF_FF_FF_FF
    time_mid = (timestamp >> 32) & 0xFF_FF
    time_hi_and_version = ((timestamp >> 48) & 0x0F_FF) | (1 << 12)
    clock_seq_low = clock_seq & 0xFF
    clock_seq_hi_and_reserved = ((clock_seq & 0x3F_00) >> 8) | 0x80
    return (
            uint32be(time_low)
            + uint16be(time_mid)
            + uint16be(time_hi_and_version)
            + uint8be(clock_seq_hi_and_reserved)
            + uint8be(clock_seq_low)
            + mac.packed
    )


class DUID(enum.Enum):
    DUID_LLT = (0x01, duid_llt)
    DUID_EN = (0x02, duid_en)
    DUID_LL = (0x03, duid_ll)
    DUID_UUID = (0x04, duid_uuid)


@pytest.fixture(
    scope='session',
    params=DUID.__members__.values(),
    ids=lambda duid_type: f'duid_type={duid_type.name}',
)
def duid(client_mac: netaddr.EUI, time: datetime.datetime, request) -> bytes:
    type_id, converter = request.param.value
    return uint8be(type_id) + converter(client_mac, time)


@pytest.fixture(scope='session', params=(b'\x00\x00\x00\x01',))
def iaid(request) -> bytes:
    return request.param


@pytest.fixture(scope='session')
def client_id(duid: bytes, iaid: bytes, request) -> bytes:
    # RFC 3315 Client Identifier
    return b'\xff' + iaid + duid


@pytest.fixture
def mock_secrets_randbits(mocker):
    tx_id = secrets.randbits(32)
    mock = mocker.patch("secrets.randbits")
    mock.return_value = tx_id
    yield mock


@pytest.fixture(scope='session')
def release_packet_factory():
    def do(
            transaction_id: int,
            server_ip: netaddr.IPAddress,
            client_ip: netaddr.IPAddress,
            client_mac: netaddr.EUI,
            client_id: Optional[bytes] = None,
    ) -> bytearray:
        message = b"Lease revoked administratively"
        options = bytearray(chain(
            # Option: (53) DHCP Message Type (Release)
            (53, 1, 7),
            # Option: (54) DHCP Server Identifier
            (54, 4,),
            server_ip.packed,
            # Option: (56) Message
            (56, len(message),),
            message,
            # Option: (61) Client identifier
            (61, len(client_id),) if client_id else (),
            client_id if client_id else (),
            # Option: (255) End
            (255,),
        ))

        packet = bytearray(chain(
            # Message type: Boot Request (1)
            uint8be(0x01),
            # Hardware type: Ethernet (0x01)
            uint8be(0x01),
            # Hardware address length
            uint8be(len(client_mac.packed)),
            # Hops
            uint8be(0x00),
            # Transaction ID
            uint32be(transaction_id),
            # Seconds elapsed
            uint16be(0x0000),
            # Bootp flags
            uint16be(0x0000),
            # Client IP address
            uint32be(client_ip.value),
            # Your (client) IP address
            uint32be(0x00000000),
            # Next server IP address
            uint32be(0x00000000),
            # Relay agent IP address
            uint32be(0x00000000),
            # Client MAC address
            client_mac.packed,
            # Client hardware address padding
            b'\x00' * (16 - len(client_mac.packed)),
            # Server host name
            b'\x00' * 64,
            # Boot file name
            b'\x00' * 128,
            # Magic cookie
            (0x63, 0x82, 0x53, 0x63,),
            # Options:
            options,
            # Padding
            b'\x00' * (308 - len(options)),
        ))
        return packet

    return do


def test_make_release(
        release_packet_factory,
        mock_secrets_randbits,
        server_ip,
        client_ip,
        client_mac,
        client_id,
):
    transaction_id = mock_secrets_randbits.return_value
    expected_packet = release_packet_factory(
        transaction_id, server_ip, client_ip, client_mac, client_id
    )
    got_packet = make_release_packet(
        server_ip, client_ip, client_mac, client_id
    )
    # Check for transaction id
    mock_secrets_randbits.assert_called_once_with(32)
    assert got_packet == expected_packet


@pytest.fixture(scope='session')
def packet(server_ip, client_ip, client_mac, time, release_packet_factory):
    """A simple test packet"""
    client_id = duid_ll(client_mac, time)
    transaction_id = 0
    return release_packet_factory(
        transaction_id, server_ip, client_ip, client_mac, client_id
    )


@pytest.fixture
def mocked_socket(mocker, packet):
    socket_class = mocker.patch("socket.socket", autospec=True)
    socket_instance = socket_class.return_value
    socket_instance.sendto.return_value = len(packet)
    return socket_class


@pytest.fixture(scope='session', params=("eth0",))
def interface(request) -> str:
    return request.param


def test_send_dhcp_packet_opens_udp_socket(
        mocked_socket,
        server_ip,
        packet,
):
    send_dhcp_packet(server_ip, packet)
    mocked_socket.assert_called_once_with(
        socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP,
    )


def test_send_dhcp_packet_sends_to_server(
        mocked_socket,
        server_ip,
        packet,
):
    send_dhcp_packet(server_ip, packet)
    mocked_socket.return_value.sendto.assert_called_once_with(
        packet, (str(server_ip), 67),
    )


def test_send_dhcp_packet_binds_to_interface(
        mocked_socket,
        server_ip,
        packet,
        interface,
):
    send_dhcp_packet(server_ip, packet, from_interface=interface)
    mocked_socket.return_value.setsockopt.assert_called_once_with(
        socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode('ascii'),
    )


def test_send_dhcp_packet_binds_to_any_ip(
        mocked_socket,
        server_ip,
        packet,
):
    send_dhcp_packet(server_ip, packet)
    mocked_socket.return_value.bind.assert_called_once_with(
        ('', 68),
    )


def test_send_dhcp_packet_binds_to_specific_ip(
        mocked_socket,
        server_ip,
        client_ip,
        packet,
):
    send_dhcp_packet(server_ip, packet, from_ip=client_ip)
    mocked_socket.return_value.bind.assert_called_once_with(
        (str(client_ip), 68),
    )

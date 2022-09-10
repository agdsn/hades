import contextlib
import ctypes
import secrets
import socket
import typing
from typing import Optional

import logging
import netaddr
from pyroute2.netns import pushns, popns

logger = logging.getLogger(__name__)


class DHCPPacket(ctypes.BigEndianStructure):
    """
    RFC 2131 DHCP packet structure
    """
    _pack_ = 1
    _fields_ = (
        ("op", ctypes.c_ubyte),
        ("htype", ctypes.c_ubyte),
        ("hlen", ctypes.c_ubyte),
        ("hops", ctypes.c_ubyte),
        ("xid", ctypes.c_uint32),
        ("secs", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("ciaddr", ctypes.c_uint32),
        ("yiaddr", ctypes.c_uint32),
        ("siaddr", ctypes.c_uint32),
        ("giaddr", ctypes.c_uint32),
        ("chaddr", ctypes.c_ubyte * 16),
        ("sname", ctypes.c_ubyte * 64),
        ("file", ctypes.c_ubyte * 128),
        ("magic_cookie", ctypes.c_uint32),
        ("options", ctypes.c_ubyte * 308),
    )


class DHCPOption(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = (
        ("tag", ctypes.c_ubyte),
        ("length", ctypes.c_ubyte),
    )


def make_release_packet(
        server_ip: netaddr.IPAddress,
        client_ip: netaddr.IPAddress,
        client_mac: netaddr.EUI,
        client_id: Optional[bytes] = None,
) -> bytearray:
    """
    Create a valid DHCPRELEASE packet for a given client IP address, client
    MAC address and server IP address.

    Optionally a client identifier can be specified too. The DHCP packet will
    contain the message option with the contents
    ``b"Lease revoked administratively"``.

    :param server_ip: IP address of the DHCP server
    :param client_ip: IP address of the DHCP client
    :param client_mac: Ethernet MAC address of the DHCP client
    :param client_id: Client identifier of the DHCP client (optional)
    :return: A DHCP packet
    """
    if server_ip.version != 4 or client_ip.version != 4:
        raise ValueError(f"Illegal IP version in ips {server_ip}, {client_ip}")
    buf = bytearray(ctypes.sizeof(DHCPPacket))
    client_mac_packed = client_mac.packed
    packet = DHCPPacket.from_buffer(buf)
    packet.op = 1  # BOOTREQUEST
    packet.htype = 1  # Ethernet
    packet.hlen = len(client_mac_packed)
    packet.xid = secrets.randbits(32)
    packet.hops = 0
    packet.secs = 0
    packet.flags = 0
    packet.ciaddr = client_ip.value
    packet.yiaddr = 0
    packet.siaddr = 0
    packet.giaddr = 0
    ctypes.memmove(packet.chaddr, client_mac_packed, len(client_mac_packed))
    ctypes.memset(packet.sname, 0, ctypes.sizeof(packet.sname))
    ctypes.memset(packet.file, 0, ctypes.sizeof(packet.file))
    packet.magic_cookie = 0x63825363
    ctypes.memset(packet.options, 0, ctypes.sizeof(packet.file))
    options = bytearray(0)
    # DHCP Message Type Option with value DHCPRELEASE
    options.extend([53, 1, 7])
    # Server Identifier Option
    options.extend([54, 4])
    options.extend(server_ip.packed)
    # Message Option
    message = b"Lease revoked administratively"
    options.extend([56, len(message)])
    options.extend(message)
    # Client Identifier Option
    if client_id is not None:
        options.extend([61, len(client_id)])
        options.extend(client_id)
    # End Option
    options.append(255)
    # ctypes can't memmove from bytearray
    options_type = ctypes.c_byte * len(options)
    ctypes.memmove(
        packet.options, options_type.from_buffer(options),
        len(options)
    )
    return buf


IP_PKTINFO = 8


# noinspection PyPep8Naming
class in_pktinfo(ctypes.Structure):
    _fields_ = (
        ("ipi_ifindex", ctypes.c_uint),
        ("ipi_spec_dst", ctypes.c_uint32),
        ("ipi_addr", ctypes.c_uint32),
    )


@contextlib.contextmanager
def netns(ns: str) -> typing.Iterator[None]:
    pushns(ns)
    try:
        yield
    finally:
        popns()


def send_dhcp_packet(
        server_ip: netaddr.IPAddress, packet: bytearray,
        from_interface: Optional[str] = None,
        from_ip: Optional[netaddr.IPAddress] = None,
):
    """
    Send a given DHCP packet as a DHCP client (port 68) to a DHCP server (port
    67).

    If no interface or IP address to send the packet from is specified, the
    operating system will choose one.

    :param server_ip: IP address of server.
    :param packet: DHCP packet
    :param from_interface: Interface to send the packet from (optional)
    :param from_ip: IP address to send the packet from (optional)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    with contextlib.closing(sock):
        if from_interface is not None:
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_BINDTODEVICE,
                from_interface.encode('ascii')
            )
        bind_address = str(from_ip) if from_ip is not None else ''
        sock.bind((bind_address, 68))
        sent = sock.sendto(packet, (str(server_ip), 67))
        if sent < len(packet):
            logger.error("Only %d of %d bytes were sent", sent, len(packet))


def release_dhcp_lease(
        server_ip: netaddr.IPAddress,
        client_ip: netaddr.IPAddress,
        client_mac: netaddr.EUI,
        client_id: Optional[bytes] = None,
        from_interface: Optional[str] = None,
        from_ip: Optional[netaddr.IPAddress] = None,
        ns: Optional[str] = 'auth',
):
    """
    Send a DHCPRELEASE packet to the given server_ip for lease of given
    client_ip and client_mac.

    An optional client identifier may also be specified.

    :param server_ip: IP address of the DHCP server
    :param client_ip: IP address of the DHCP client
    :param client_mac: MAC address of the DHCP client
    :param client_id: Client identifier (optional)
    :param from_interface: Interface to send the packet from (optional)
    :param from_ip: IP address to send the packet from (optional)
    :param ns: the netns you want to enter before sending the packet
    """
    packet = make_release_packet(server_ip, client_ip, client_mac, client_id)
    # We need to send the packet while in the `auth` netns, because that's where the DNSMasq listens on
    # (specifically,`eth2`).  Although `eth2` is available in the `root` netns as `auth-eth2@…`,
    # there is no route to the IP the dnsmasq listens on (or at least, its existence is not guaranteed).
    #
    # fun fact: this may have caused multiple DHCPRELEASEs to target the production hades instance
    # because that's just where the `default` route directs you if you're in the office. Oops.
    with netns(ns) if ns else contextlib.nullcontext():
        send_dhcp_packet(server_ip, packet, from_interface, from_ip)

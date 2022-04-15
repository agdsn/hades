from unittest.mock import MagicMock

import netaddr
import pytest
from netaddr import EUI, IPAddress

from hades.bin.dhcp_script import perform_lease_update, obtain_lease_info, \
    LeaseArguments
from hades.common.db import auth_dhcp_lease

r"""
This tests the functionality that is responsible to persist the `dnsmasq`
lease events to the database.

This happens via an invocation of the form ``$ENV hades-dhcp-script $VERB $MAC $IP``,
e.g.

.. code-block :: shell-script

    DNSMASQ_CLIENT_ID=01:50:7b:9d:87:76:4b \
    DNSMASQ_INTERFACE=eth2 \
    DNSMASQ_LEASE_EXPIRES=1508969413 \
    DNSMASQ_RELAY_ADDRESS=141.76.121.1 \
    DNSMASQ_REMOTE_ID=$'\024XВ5' \
    DNSMASQ_SUPPLIED_HOSTNAME=$'\315\365\314\354\263\376' \
    DNSMASQ_TAGS=Bor34\ known\ eth2 \
    DNSMASQ_TIME_REMAINING=86400 \
    DNSMASQ_VENDOR_CLASS=MSFT\ 5.0 \
    /var/lib/hades/auth-dhcp/dhcp-script.sh
    add 00:de:ad:be:ef:00 141.76.121.2

"""


def to_binary(environ: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode('utf-8'): v.encode('utf-8') for k, v in environ.items()}


def test_obtain_lease_info():
    env_dict = {f"DNSMASQ_{k.upper()}": v for k, v in {
        'client_id': '01:50:7b:9d:87:76:4b',
        'interface': 'eth2',
        'relay_address': '141.76.121.1',
        'remote_id': '\024xb5',
        'supplied_hostname': 'My fancy Laptop',
        'tags': 'Bor34 known eth2',
        'time_remaining': '86400',
        'vendor_class': 'MSFT 5.0',
    }.items()}

    info = obtain_lease_info(
        args=LeaseArguments(
            mac=EUI('00:de:ad:be:ef:00'),
            ip=IPAddress('141.76.121.2'),
            hostname=None,
        ),
        environ=env_dict,
        environb=to_binary(env_dict),
        missing_as_none=False
    )

    assert info is not None
    KEYS = {'ClientID', 'ExpiresAt', 'IPAddress', 'MAC', 'SuppliedHostname', 'Tags', 'RemoteID',
            'VendorClass', 'RelayIPAddress'}
    assert set(info.keys()) == KEYS
    for key in KEYS:
        assert info.get(key) is not None, f"info[{key}] is not Set!"


def test_add_lease():
    pass

@pytest.fixture
def conn_mock():
    conn = MagicMock()
    result_mock = MagicMock()
    result_mock.rowcount = 1
    conn.execute.return_value = result_mock
    return conn


def test_trivial_lease_update_does_nothing(conn_mock):
    values = {
        # TODO find a more representative set of values
        'DNSMASQ_CLIENT_ID': '01:50:7b:9d:87:76:4b',
    }
    result = perform_lease_update(
        conn_mock,
        dhcp_lease_table=auth_dhcp_lease,
        ip=netaddr.IPAddress('141.30.1.1'),
        mac=netaddr.EUI('00:de:ad:be:ef:00'),
        old=values,
        new=values,
    )
    assert conn_mock.execute.mock_calls == []
    assert result is None

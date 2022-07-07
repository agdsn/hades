# -*- coding: utf-8 -*-
import operator
from functools import partial
from typing import Any, Callable, Iterable, Optional, Tuple, Union

from kombu.exceptions import ContentDisallowed, SerializerNotInstalled
from kombu.serialization import registry
import nacl.bindings
import nacl.encoding
import nacl.exceptions
import nacl.signing
import pytest

from hades.agent.signature import ED25519Serializer, register_armored, register_raw

dual_serializer_factory = Callable[
    [str, Optional[Iterable[str]], bool],
    Tuple[ED25519Serializer, ED25519Serializer]
]

single_serializer_factory = Callable[
    [str, Optional[Iterable[str]], bool],
    ED25519Serializer
]


@pytest.fixture(scope='session')
def alice_key() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey.generate()


@pytest.fixture(scope='session')
def bob_key() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey.generate()


@pytest.fixture(scope='session')
def carol_key() -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey.generate()


@pytest.fixture(scope='session')
def make_dual_serializers(alice_key, bob_key) -> dual_serializer_factory:
    def _make_serializers(
            inner_serializer: str, accept: Optional[Iterable[str]] = None, armored: bool = False,
    ) -> Tuple[ED25519Serializer, ED25519Serializer]:
        """Create ed25519 serializers with a given inner serializer with mutual trust between Alice and Bob"""
        alice_serializer = ED25519Serializer(alice_key, [bob_key.verify_key], inner_serializer, accept, armored)
        bob_serializer = ED25519Serializer(bob_key, [alice_key.verify_key], inner_serializer, accept, armored)
        return alice_serializer, bob_serializer

    return _make_serializers


@pytest.fixture(scope='session')
def make_single_serializer(carol_key) -> single_serializer_factory:
    def _make_serializer(
            serializer: str, accept: Optional[Iterable[str]] = None, armored: bool = False,
    ) -> ED25519Serializer:
        return ED25519Serializer(carol_key, [carol_key.verify_key], serializer, accept, armored)
    return _make_serializer


@pytest.fixture(params={
    'raw': [
            'secret string message',
            b'secret bytes message'
        ],
    'json': [
        'test',
        1,
        3.14,
        True,
        False,
        None,
        {
            'string': 'test',
            'int': 1,
            'float': 3.14,
            'True': True,
            'False': True,
            'None': None,
            'list': ['test', 1, 3.14, True, False, None],
            'dict': {
                'de': 'Heizölrückstoßabdämpfung',
                'hu': 'Árvíztűrő tükörfúrógép',
                'el': 'Ξεσκεπάζω τὴν ψυχοφθόρα βδελυγμία',
            },
        },
    ]
}.items(), ids=operator.itemgetter(0))
def test_values(request) -> Tuple[str, Any]:
    return request.param


@pytest.mark.parametrize(
    'armored',
    (True, False),
    ids=('raw', 'armored'),
)
def test_serdes_with_dual_keys(
        test_values: Tuple[str, Any],
        make_dual_serializers: dual_serializer_factory,
        armored: bool,
):
    inner_serializer, values = test_values
    alice_serializer, bob_serializer = make_dual_serializers(inner_serializer, armored=armored)
    for value in values:
        message = alice_serializer.serialize(value)
        assert value == bob_serializer.deserialize(message)


@pytest.mark.parametrize(
    'armored',
    (True, False),
    ids=('raw', 'armored'),
)
def test_serdes_with_single_key(
        test_values: Tuple[str, Any],
        make_single_serializer: single_serializer_factory,
        armored: bool,
):
    inner_serializer, values = test_values
    serializer = make_single_serializer(inner_serializer, armored=armored)

    for data in values:
        serialized_data = serializer.serialize(data)
        assert data != serialized_data
        deserialized_data = serializer.deserialize(serialized_data)
        assert serialized_data != deserialized_data
        assert data == deserialized_data


def test_accept(make_single_serializer):
    # Serialize with the json serializer, but accept only raw strings or bytes
    serializer = make_single_serializer(
        'json', ['application/data', 'application/text']
    )
    data = 'secret message'
    serialized_data = serializer.serialize(data)
    with pytest.raises(ContentDisallowed):
        serializer.deserialize(serialized_data)


def test_invalid_signature(make_single_serializer):
    serializer = make_single_serializer('raw')
    data = 'secret message'
    serialized_data = bytearray(serializer.serialize(data))
    for i in range(nacl.bindings.crypto_sign_BYTES):
        with pytest.raises(nacl.exceptions.BadSignatureError):
            orig = serialized_data[i]
            serialized_data[i] = ~orig & 0xff
            serializer.deserialize(bytes(serialized_data))
            serialized_data[i] = orig


def test_unknown_signer(
        make_single_serializer: single_serializer_factory,
        make_dual_serializers: dual_serializer_factory,
):
    alice, bob = make_dual_serializers('raw')
    carol = make_single_serializer('raw')
    carols_message = carol.serialize(b'secret message')
    with pytest.raises(ValueError):
        alice.deserialize(carols_message)


@pytest.mark.parametrize(
    'register_func',
    (register_raw, register_armored),
    ids=('raw', 'armored'),
)
def test_register(
        make_dual_serializers: dual_serializer_factory,
        register_func: partial,
):
    inner_serializer = 'raw'
    accept = [inner_serializer]
    expected_data = 'secret message'
    name = register_func.keywords['name']
    armored = register_func.keywords['armored']
    expected_content_type = register_func.keywords['content_type']
    alice_serializer, bob_serializer = make_dual_serializers(inner_serializer, accept, armored)
    with pytest.raises(SerializerNotInstalled):
        registry.dumps(expected_data, name)
    try:
        register_func(
            alice_serializer._signing_key, bob_serializer._verify_keys,
            inner_serializer=inner_serializer, accept=accept,
        )
        got_content_type, got_content_encoding, got_payload = registry.dumps(expected_data, name)
    finally:
        registry.unregister(name)
    assert expected_content_type == got_content_type
    assert 'binary' == got_content_encoding
    assert expected_data == bob_serializer.deserialize(got_payload)

# -*- coding: utf-8 -*-
"""
A serializer that encodes data using another inner serializer and signs the
encoded binary data with an ed25519 signature. A single inner serializer can be
specified for serialization, but multiple inner serializers can be configured
for deserialization.

The binary data encoded by the inner serializer is prepended with the signature,
the public key that produced the signature message, the content type and the
content encoding of the inner serializer. The content type and the content
encoding are delimited by a null byte (\x00).

The output of the inner serializer is left as is as payload without any
additional encoding.

.. code-block :: text

    +-----------------------------+----+  <--+
    | Signature (64 bytes)             |     |
    |                                  |     H
    +--------------------------------- +     e   <--+
    | Signer (32 bytes)                |     a      M
    +--------------------------------- +     d      e
    | Content Type (variable)     | 00 |     e      s
    +-----------------------------+----+     r      s
    | Content Encoding (variable) | 00 |     |      a
    +-----------------------------+----+  <--+      g
    | Payload (variable)               |            e
    +----------------------------------+         <--+

The signature is computed over everything (including signer, content type,
content encoding).

The header may be armored by encoding it using base 64 (without newlines) and
placing newline (\n) between header and payload:

.. code-block :: text

    +-----------------------------+----+
    | Header (variable, base 64)  | \n |
    +--------------------------------- +
    | Payload (variable)               |
    +----------------------------------+

"""
import base64
import typing as t
from functools import partial
from typing import Iterable, Optional, Union

import nacl.bindings
import nacl.encoding
import nacl.signing
from kombu.serialization import dumps, loads, registry

__all__ = ("ED25519Serializer", "register", "register_armored", "register_raw")
# Extracts signer from a raw signed message
from hades.common.util import qualified_name

SIGNER_SLICE = slice(
    nacl.bindings.crypto_sign_BYTES,
    nacl.bindings.crypto_sign_BYTES + nacl.bindings.crypto_sign_PUBLICKEYBYTES
)
# Extracts message from a signed message
MESSAGE_SLICE = slice(
    nacl.bindings.crypto_sign_BYTES + nacl.bindings.crypto_sign_PUBLICKEYBYTES,
    None
)


class ED25519Serializer:
    def __init__(
            self, signing_key: nacl.signing.SigningKey,
            verify_keys: Iterable[nacl.signing.VerifyKey],
            inner_serializer: str = "json",
            accept: Optional[Iterable] = None,
            armored: bool = False,
    ):
        # Create copies of keys with raw encoder
        self._signing_key = nacl.signing.SigningKey(bytes(signing_key))
        self._signer = bytes(signing_key.verify_key)
        self._verify_keys = {
            bytes(key): nacl.signing.VerifyKey(bytes(key))
            for key in verify_keys
        }
        self._inner_serializer = inner_serializer
        self._accept = frozenset(accept) if accept else None
        self._armored = armored

    @staticmethod
    def _ensure_bytes(data: Union[bytes, str], content_encoding: str) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        elif isinstance(data, str):
            return data.encode(content_encoding)
        elif isinstance(data, memoryview):
            return data.tobytes()
        else:
            raise TypeError(
                f"Argument should be bytes, bytearray, str, or memoryview, "
                f"not {qualified_name(type(data))}"
            )

    def serialize(self, data: t.Any) -> bytes:
        content_type, content_encoding, payload = dumps(
            data, serializer=self._inner_serializer
        )
        bytes_payload = self._ensure_bytes(payload, content_encoding)
        content_type = self._ensure_bytes(content_type, "us-ascii")
        content_encoding = self._ensure_bytes(content_encoding, "us-ascii")
        message = b"".join(
            (
                self._signer,
                content_type,
                b"\x00",
                content_encoding,
                b"\x00",
                bytes_payload,
            )
        )
        signed_message = t.cast(bytes, self._signing_key.sign(message))
        if self._armored:
            return (
                base64.b64encode(signed_message[: -len(bytes_payload)])
                + b"\n"
                + bytes_payload
            )
        else:
            return signed_message

    def deserialize(self, data: bytes) -> t.Any:
        if self._armored:
            header, sep, payload = data.partition(b"\n")
            if not sep:
                raise ValueError("Invalid message: Expected armored header")
            header = base64.b64decode(header, validate=True)
            data = header + payload
        signer = data[SIGNER_SLICE]

        try:
            verify_key = self._verify_keys[signer]
        except KeyError:
            raise ValueError("Unknown signer {!r}".format(signer)) from None
        message = verify_key.verify(data)
        # Skip signer
        message = message[nacl.bindings.crypto_sign_PUBLICKEYBYTES:]

        try:
            content_type, content_encoding, payload = message.split(
                b"\x00", maxsplit=2
            )
        except ValueError:
            raise ValueError(
                "Invalid message: No content_type/content_encoding before "
                "payload"
            ) from None
        content_type = content_type.decode("us-ascii")
        content_encoding = content_encoding.decode("us-ascii")
        return loads(
            payload, content_type, content_encoding,
            accept=self._accept,
        )


def register(
        signing_key: nacl.signing.SigningKey,
        verify_keys: Iterable[nacl.signing.VerifyKey],
        name: str,
        content_type: str,
        armored: bool,
        *,
        inner_serializer: str = "json",
        accept: Optional[Iterable[str]] = ("application/json",),
) -> None:
    """
    Register serializer with :mod:`kombu`.

    :param signing_key: The key used for signing serialized messages
    :param verify_keys: The keys used for verifying messages before
     deserialization
    :param inner_serializer: The serializer to use for serializing the data
     before signing
    :param accept: If not :obj:`None` an iterable of content types that may be
     decoded
    :param name: Name of the serializer
    :param content_type: Content type of the serializer
    :param armored: Specifies whether the leading signature header should be
     base64 encoded
    """
    s = ED25519Serializer(
        signing_key, verify_keys, inner_serializer, accept, armored,
    )
    registry.register(
        name, s.serialize, s.deserialize, content_type, "binary",
    )


register_raw = partial(
    register,
    name="ed25519",
    content_type="application/x.data.ed25519",
    armored=False,
)
register_armored = partial(
    register,
    name="ed25519.armored",
    content_type="application/x.data.ed25519.armored",
    armored=True,
)

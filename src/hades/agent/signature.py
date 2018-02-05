# -*- coding: utf-8 -*-
"""
A serializer that prepends a JSON header with an ed25519 signature before the
data.

The header is a completely separate JSON document, that is separated from the
body by optional whitespace. This allows parsing the header without parsing the
payload. Also it is not required to encode the payload. Raw data can also be
inspected by humans easily. The only problem with this scheme is, that the
payload may not start with space, because this white space would be striped
and signature verification would fail.

The JSON payload ``{"Foobar": 1}`` would be encoded as follows:

.. code-block :: json

    {
      "signature": "u9rPWbQh3TNpW8wrimL5SHtelkgm32cTPfzaUgp+djMDGz/Vjf/mb6BtQcXpJ1noJl2xILTWxhrpqtv9ykf2Bw==",
      "signer": "w7ADgLSZTlXIDY/qbcfxUCeXht8VcpGoJYOj0lQu1Qw=",
      "content_type": "application/json",
      "content_encoding": "utf-8"
    }
    {
      "Foobar": 1
    }

"""
import io
import json
from typing import Iterable, Union

import nacl.encoding
import nacl.signing
from kombu.serialization import dumps, loads, register as kombu_register
from kombu.utils.encoding import bytes_to_str

__all__ = ['ED25519Serializer', 'register']


class ED25519Serializer(object):
    key_codec = nacl.encoding.Base64Encoder()
    json_decoder = json.JSONDecoder()
    whitespace = b' \t\n\r'

    def __init__(self, signing_key: nacl.signing.SigningKey,
                 verify_keys: Iterable[nacl.signing.VerifyKey],
                 serializer='json', content_encoding='utf-8'):
        self._signing_key = signing_key
        self._verify_keys = {
            self.key_codec.encode(bytes(key)).decode('ascii'): key
            for key in verify_keys
        }
        self._serializer = serializer
        self._signer = self.key_codec.encode(
            bytes(self._signing_key.verify_key)).decode('ascii')
        self._content_encoding = content_encoding

    def _ensure_bytes(self, data: Union[bytes, str]):
        if isinstance(data, bytes):
            return data
        return data.encode(self._content_encoding)

    def serialize(self, data):
        content_type, content_encoding, body = dumps(
            data, serializer=self._serializer)
        if content_encoding != self._content_encoding:
            raise ValueError("Content encoding of inner serializer {!r} must "
                             "match ({!r} != {!r})"
                             .format(self._serializer, content_encoding,
                                     self._content_encoding))
        body = self._ensure_bytes(body)
        if len(body) > 0 and body[0] in self.whitespace:
            raise ValueError("Inner data may not begin with the following "
                             "characters {!r}"
                             .format(str(self.whitespace)))
        message = self._signing_key.sign(body)
        signature = self.key_codec.encode(message.signature).decode('ascii')
        header = {
            'signature':        signature,
            'signer':           self._signer,
            'content_type':     content_type,
            'content_encoding': content_encoding,
        }
        buffer = io.BytesIO()
        wrapper = io.TextIOWrapper(buffer, self._content_encoding,
                                   write_through=True)
        with wrapper:
            json.dump(header, wrapper)
            buffer.write(b"\n")
            buffer.write(message.message)
            return buffer.getvalue()

    def parse_header(self, data):
        return self.json_decoder.raw_decode(data.decode(self._content_encoding))

    def deserialize(self, data):
        data = self._ensure_bytes(data)
        header, end = self.parse_header(data)
        # Skip whitespace
        length = len(data)
        while end < length and data[end] in self.whitespace:
            end += 1
        header, body = header, data[end:]

        signer, signature, content_type, content_encoding = (
            header['signer'], header['signature'],
            header['content_type'], header['content_encoding']
        )
        signature = self.key_codec.decode(signature)
        if content_encoding != self._content_encoding:
            raise ValueError("Invalid inner content encoding ({!r} != {!r})"
                             .format(content_encoding, self._content_encoding))

        try:
            verify_key = self._verify_keys[signer]
        except KeyError:
            raise ValueError("Unknown signer {!r}".format(signer)) from None
        verify_key.verify(body, signature)
        return loads(bytes_to_str(body), content_type, content_encoding,
                     force=True)


def register(signing_key: nacl.signing.SigningKey,
             verify_keys: Iterable[nacl.signing.VerifyKey],
             name: str = 'ed25519', serializer='json',
             content_type: str = 'application/x-data-ed25519',
             content_encoding: str = 'utf-8'):
    """Register serializer with :mod:`kombu`"""
    s = ED25519Serializer(signing_key, verify_keys, serializer,
                          content_encoding)
    kombu_register(name, s.serialize, s.deserialize, content_type,
                   content_encoding)

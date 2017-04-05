from base64 import b64decode, b64encode
from binascii import unhexlify
from hashlib import sha256 as _sha256
from os import urandom

from coincurve.context import GLOBAL_CONTEXT
from ._libsecp256k1 import ffi, lib

GROUP_ORDER = (b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
               b'\xfe\xba\xae\xdc\xe6\xafH\xa0;\xbf\xd2^\x8c\xd06AA')
KEY_SIZE = 32
ZERO = b'\x00'
PEM_HEADER = b'-----BEGIN PRIVATE KEY-----\n'
PEM_FOOTER = b'-----END PRIVATE KEY-----\n'


if hasattr(int, "from_bytes"):
    def bytes_to_int(bytestr):
        return int.from_bytes(bytestr, 'big')
else:
    def bytes_to_int(bytestr):
        return int(bytestr.encode('hex'), 16)


if hasattr(int, "to_bytes"):
    def int_to_bytes(num):
        return num.to_bytes((num.bit_length() + 7) // 8 or 1, 'big')
else:
    def int_to_bytes(num):
        hexed = '{:x}'.format(num)

        # Handle odd-length hex strings.
        if len(hexed) & 1:
            hexed = '0' + hexed

        return unhexlify(hexed)


def sha256(bytestr):
    return _sha256(bytestr).digest()


def chunk_data(data, size):
    return (data[i:i + size] for i in range(0, len(data), size))


def der_to_pem(der):
    return b''.join([
        PEM_HEADER,
        b'\n'.join(chunk_data(b64encode(der), 64)), b'\n',
        PEM_FOOTER
    ])


def pem_to_der(pem):
    return b64decode(
        pem.strip()[28:-25].replace(b'\n', b'')
    )


def get_valid_secret():
    while True:
        secret = urandom(KEY_SIZE)
        if ZERO < secret <= GROUP_ORDER:
            return secret


def pad_scalar(scalar):
    return (ZERO * (KEY_SIZE - len(scalar))) + scalar[-KEY_SIZE:]


def validate_secret(secret):
    if not ZERO < secret <= GROUP_ORDER:
        raise ValueError('Secret scalar must be greater than 0 and less than '
                         'or equal to the group order.')
    return pad_scalar(secret)


def verify_signature(signature, message, public_key, hasher=sha256, context=GLOBAL_CONTEXT):
    length = len(public_key)
    if length not in (33, 65):
        raise ValueError('{} is an invalid length for a public key.'
                         ''.format(length))

    pubkey = ffi.new('secp256k1_pubkey *')

    res = lib.secp256k1_ec_pubkey_parse(
        context.ctx, pubkey, public_key, length
    )
    assert res == 1

    msg_hash = hasher(message)
    if len(msg_hash) != 32:
        raise ValueError('Message hash must be 32 bytes long.')

    sig = ffi.new('secp256k1_ecdsa_signature *')

    res = lib.secp256k1_ecdsa_signature_parse_der(
        context.ctx, sig, signature, len(signature)
    )
    assert res == 1

    verified = lib.secp256k1_ecdsa_verify(
        context.ctx, sig, msg_hash, pubkey
    )

    # A performance hack to avoid global bool() lookup.
    return not not verified

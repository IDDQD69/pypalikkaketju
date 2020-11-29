import binascii
import json

from nacl.bindings import crypto_sign


def sign_data(secret_key, data):
    data_str = data

    if isinstance(data, dict):
        data_str = json.dumps(data)

    data_bytes = bytes(data_str, 'utf-8')
    secret_key_bytes = binascii.unhexlify(secret_key)
    signed_data_bytes = crypto_sign(data_bytes, secret_key_bytes)
    return signed_data_bytes.hex()

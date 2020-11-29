import binascii
import json

from nacl.bindings import crypto_sign


def sign_data(secret_key, data):
    data_str = data
    if isinstance(data, dict):
        data_str = json.dumps(data)
    data_bytes = bytes(data_str, 'utf-8') # binascii.unhexlify(data_str)
    secret_key_bytes = binascii.unhexlify(secret_key)
    return crypto_sign(data_bytes, secret_key_bytes)

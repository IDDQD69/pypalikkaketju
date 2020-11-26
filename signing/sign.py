import json

from nacl.bindings import crypto_sign
from nacl.encoding import HexEncoder

# sign_key = sys.argv[1]
# sign_message = ' '.join(sys.argv[2:])
# sign_message = bytes(sign_message, 'utf-8')
# signing_key = SigningKey(sign_key, encoder=HexEncoder)
# signed_message = signing_key.sign(sign_message, encoder=HexEncoder)


def sign_data(secret_key, data):
    print('sc', secret_key)
    print('data', data)

    data_str = data
    if isinstance(data, dict):
        data_str = json.dumps(data)
    data_bytes = bytes(data_str, 'utf-8')

    signed_message = crypto_sign(data_bytes, secret_key)

    return signed_message
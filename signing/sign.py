import sys
import json
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey

sign_key = sys.argv[1]
sign_message = ' '.join(sys.argv[2:])
sign_message = bytes(sign_message, 'utf-8')
signing_key = SigningKey(sign_key, encoder=HexEncoder)
signed_message = signing_key.sign(sign_message, encoder=HexEncoder)


def sign_data(secret_key, data):

    sk = SigningKey(secret_key)
    string_to_sign = data
    if isinstance(data, dict):
        string = json.dumps(data)
    return ''
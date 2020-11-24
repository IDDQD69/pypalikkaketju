import sys

from nacl.encoding import HexEncoder
from nacl.signing import SigningKey

sign_key = sys.argv[1]
sign_message = ' '.join(sys.argv[2:])
sign_message = bytes(sign_message, 'utf-8')
signing_key = SigningKey(sign_key, encoder=HexEncoder)
signed_message = signing_key.sign(sign_message, encoder=HexEncoder)

from nacl.encoding import HexEncoder
from nacl.encoding import Base64Encoder

from nacl.signing import SigningKey
from nacl.signing import VerifyKey

import sys

sign_key = sys.argv[1]
sign_message = ' '.join(sys.argv[2:])
sign_message = bytes(sign_message, 'utf-8')

signing_key = SigningKey(sign_key, encoder=HexEncoder)
signed_message = signing_key.sign(sign_message, encoder=HexEncoder)
print('signed hex', signed_message)

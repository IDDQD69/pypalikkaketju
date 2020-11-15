from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
from nacl.encoding import Base64Encoder
from nacl.encoding import URLSafeBase64Encoder

from nacl.signing import VerifyKey

signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

sk_hex = signing_key.encode(encoder=HexEncoder)
vk_hex = verify_key.encode(encoder=HexEncoder)

print('privatekey', sk_hex)
print('publickey', vk_hex)

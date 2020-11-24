from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
signing_key = SigningKey.generate()
verify_key = signing_key.verify_key
sk_hex = signing_key.encode(encoder=HexEncoder)
vk_hex = verify_key.encode(encoder=HexEncoder)

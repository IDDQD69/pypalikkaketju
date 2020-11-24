from nacl.encoding import HexEncoder
from nacl.signing import VerifyKey


def verify_data(data_hex, key_hex):
    given_vk = VerifyKey(key_hex, encoder=HexEncoder)
    return given_vk.verify(data_hex, encoder=HexEncoder)

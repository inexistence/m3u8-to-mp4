from core.decrypt.ts_decrypt import TsDecrypt
from core.decrypt.ts_decrypt_aes_128 import TsDecrypt_AES128_CBC

METHOD_AES_128='AES-128'

def get_decryption(method: str, value: str, iv: str|None|bytes) -> TsDecrypt|None:
    if method == METHOD_AES_128:
        return TsDecrypt_AES128_CBC(key=value, iv=iv)
    return TsDecrypt()
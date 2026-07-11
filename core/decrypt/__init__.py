"""根据 m3u8 #EXT-X-KEY 声明的方法名创建对应解密器。"""
from core.decrypt.ts_decrypt import TsDecrypt
from core.decrypt.ts_decrypt_aes_128 import TsDecrypt_AES128_CBC

METHOD_AES_128='AES-128'

def get_decryption(method: str, value: str, iv: str|None|bytes, iv_mode: str = 'auto') -> TsDecrypt|None:
    """按 METHOD 字段选择解密实现，未知方法回退为无解密（原样返回）。"""
    if method == METHOD_AES_128:
        return TsDecrypt_AES128_CBC(key=value, iv=iv, iv_mode=iv_mode)
    return TsDecrypt()

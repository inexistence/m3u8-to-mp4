from core.decrypt.ts_decrypt import TsDecrypt
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class TsDecrypt_AES128_CBC(TsDecrypt):
    def __init__(self, key: str, iv: bytes|str|None = None):
        if isinstance(key, str):
            self.key = key.encode('utf-8')
        elif isinstance(key, bytes):
            self.key = key
        
        if isinstance(iv, str):
            iv = iv.strip('0x')
            self.iv = bytes.fromhex(iv)
        else:
            self.iv = iv

    def decrypt(self, data, iv=None):
        # 提取前16字节作为IV
        if iv is None:
            iv = data[:AES.block_size]
        # 剩余部分是真正要解密的密文
        actual_ciphertext = data[AES.block_size:]
        # 创建解密器
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        # 解密密文
        decrypted_data_padded = cipher.decrypt(actual_ciphertext)
        # 去除PKCS7填充
        try:
            decrypted_data = unpad(decrypted_data_padded, AES.block_size)
        except Exception:
            print('wrong: decrypt unpad faield, may return padded data')
            return decrypted_data_padded
        return decrypted_data

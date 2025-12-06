from core.decrypt.ts_decrypt import TsDecrypt
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class TsDecrypt_AES128_CBC(TsDecrypt):
    def __init__(self, key: str):
        if isinstance(key, str):
            self.key = key.encode('utf-8')
        elif isinstance(key, bytes):
            self.key = key

    def decrypt(self, data):
        # 提取前16字节作为IV
        iv = data[:AES.block_size]
        # 剩余部分是真正要解密的密文
        actual_ciphertext = data[AES.block_size:]
        # 创建解密器
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        # 解密密文
        decrypted_data_padded = cipher.decrypt(actual_ciphertext)
        # 去除PKCS7填充
        decrypted_data = unpad(decrypted_data_padded, AES.block_size)
        return decrypted_data

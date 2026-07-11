"""TS 分片解密策略的抽象接口。"""


class TsDecrypt:
    """解密器基类。未加密流直接原样返回，加密流由子类实现具体算法。"""

    def decrypt(self, data):
        return data

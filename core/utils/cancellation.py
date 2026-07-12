"""转换取消。"""


class ConversionCancelled(Exception):
    """用户请求取消转换。"""

    def __init__(self, message: str = '用户取消') -> None:
        super().__init__(message)

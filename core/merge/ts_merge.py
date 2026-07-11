"""TS 分片合并的抽象接口。"""


class TsMerger:
    """TS 分片合并器基类，定义 start / append / finish 三阶段生命周期。

    解析器每处理一个 .ts 分片就调用 append，由具体实现决定写入文件或管道。
    """

    def start(self):
        return

    def set_progress_total(self, total: int):
        return

    def append(self, data: bytearray):
        return

    def finish(self):
        return

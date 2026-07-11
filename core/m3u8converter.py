"""m3u8 转 MP4 的流程编排。

负责串联主播放列表选流、媒体播放列表解析、分片合并等步骤，本身不直接解析 m3u8 内容。
"""
from pathlib import Path

from core.merge.ffmpeg_merge import FfmpegMerger
from core.m3u8_stream import M3U8StreamInfoParser
from core.m3u8_ts_parser import SimpleM3U8TsParser
from core.utils.config import GlobalConfig
from core.utils.output import resolve_unique_output_path


class M3U8Converter:
    """m3u8 转换入口：选流 → 解析分片 → 输出 MP4。

    输入可以是主播放列表（多码率）或媒体播放列表（直接引用 .ts）。
    具体解析工作委托给 M3U8StreamInfoParser 和 SimpleM3U8TsParser。
    """
    def __init__(self, m3u8_index_file_path: str | Path, config: GlobalConfig):
        self.m3u8_index_file_path: Path = (
            Path(m3u8_index_file_path) if not isinstance(m3u8_index_file_path, Path) else m3u8_index_file_path
        )
        self.dir: Path = Path(m3u8_index_file_path).resolve().parent
        self.config = config
        self.m3u8_stream_info_parser = M3U8StreamInfoParser(self.m3u8_index_file_path)

    def print_stream_info(self):
        self.m3u8_stream_info_parser.print_stream_info()

    def convert(self, stream_index: int | None = None):
        self.m3u8_stream_info_parser.parse()
        streams = self.m3u8_stream_info_parser.streams

        if streams and stream_index is not None:
            if 0 <= stream_index < len(streams):
                ts_infos_index_file_path = streams[stream_index].index_file
            else:
                raise IndexError(f'stream_index {stream_index} out of range (0-{len(streams) - 1})')
        elif streams:
            ts_infos_index_file_path = self.m3u8_stream_info_parser.select_stream(self.config.stream_selection)
        else:
            ts_infos_index_file_path = None

        # 非主播放列表时 select_stream 返回 None，直接使用当前索引文件
        if ts_infos_index_file_path is None:
            ts_infos_index_file_path = self.m3u8_index_file_path

        out_put_file_name = self.config.output_file_name
        if out_put_file_name == '__DIR_NAME__':
            out_put_file_name = self.dir.name

        output_path = resolve_unique_output_path(self.dir, out_put_file_name, self.m3u8_index_file_path)
        print(f'output: {output_path}')

        merger = FfmpegMerger(output_path)
        ts_parser = SimpleM3U8TsParser(ts_infos_index_file_path, merger, aes_iv_mode=self.config.aes_iv_mode)
        ts_parser.set_skip_first_part(self.config.skip_first_part)
        ts_parser.set_reset_decryption_if_part_changed(self.config.reset_decryption_if_part_changed)
        ts_parser.merge()
        print('convert end')

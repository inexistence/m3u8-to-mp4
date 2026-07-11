"""主播放列表（多码率）解析与流选择。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import core.utils.file as file
from core.utils.value import safe_int

KEY_EXT_X_STREAM_INF = '#EXT-X-STREAM-INF:'
KEY_PROGRAM_ID = 'PROGRAM-ID'
KEY_BANDWIDTH = 'BANDWIDTH'
KEY_RESOLUTION = 'RESOLUTION'

STREAM_SELECTION_HIGHEST = 'highest_bandwidth'
STREAM_SELECTION_LOWEST = 'lowest_bandwidth'
STREAM_SELECTION_FIRST = 'first'
STREAM_SELECTION_INTERACTIVE = 'interactive'


@dataclass
class StreamVariant:
    """主播放列表中的一条码率流。

    由 #EXT-X-STREAM-INF 行与紧随其后的子 m3u8 路径配对而成。
    """
    bandwidth: int = 0
    resolution: str = ''
    program_id: int = 0
    index_file: Path | None = None


def _prompt_stream_selection(streams: list[StreamVariant]) -> StreamVariant:
    default = max(streams, key=lambda s: s.bandwidth)
    default_idx = streams.index(default)

    print(f'found {len(streams)} streams:')
    for i, stream in enumerate(streams):
        resolution = stream.resolution.replace('"', '') or 'unknown'
        bandwidth = stream.bandwidth or 'unknown'
        name = stream.index_file.name if stream.index_file else 'unknown'
        suffix = ' (default)' if i == default_idx else ''
        print(f'  [{i}] {resolution}  bandwidth={bandwidth}  {name}{suffix}')

    while True:
        raw = input(f'Select stream [0-{len(streams) - 1}] (Enter={default_idx}): ').strip()
        if raw == '':
            return streams[default_idx]
        try:
            idx = int(raw)
            if 0 <= idx < len(streams):
                return streams[idx]
        except ValueError:
            pass
        print('invalid choice, try again')


def select_stream_variant(streams: list[StreamVariant], strategy: str) -> StreamVariant | None:
    """按配置策略从多条码率流中选出一条。streams 为空时返回 None。"""
    if not streams:
        return None
    if len(streams) == 1:
        return streams[0]

    strategy = strategy.strip()
    if strategy == STREAM_SELECTION_INTERACTIVE:
        return _prompt_stream_selection(streams)
    if strategy == STREAM_SELECTION_HIGHEST:
        return max(streams, key=lambda s: s.bandwidth)
    if strategy == STREAM_SELECTION_LOWEST:
        return min(streams, key=lambda s: s.bandwidth if s.bandwidth > 0 else float('inf'))
    if strategy == STREAM_SELECTION_FIRST:
        return streams[0]
    if strategy.startswith('resolution:'):
        target = strategy.split(':', 1)[1].strip()
        for stream in streams:
            if target in stream.resolution.replace('"', ''):
                return stream
        print(f'resolution {target} not found, fallback to highest_bandwidth')
        return max(streams, key=lambda s: s.bandwidth)
    if strategy.startswith('index:'):
        idx = safe_int(strategy.split(':', 1)[1])
        if 0 <= idx < len(streams):
            return streams[idx]
        print(f'index {idx} out of range, fallback to highest_bandwidth')
        return max(streams, key=lambda s: s.bandwidth)

    print(f'unknown stream_selection "{strategy}", fallback to highest_bandwidth')
    return max(streams, key=lambda s: s.bandwidth)


class M3U8StreamInfoParser:
    """主播放列表解析器：提取多码率流并按策略选择其一。

    仅处理含 #EXT-X-STREAM-INF 的 m3u8；纯媒体播放列表解析后 streams 为空。
    """
    def __init__(self, m3u8_index_file_path: str | Path):
        if isinstance(m3u8_index_file_path, Path):
            self.m3u8_index_file_path = m3u8_index_file_path
        else:
            self.m3u8_index_file_path = Path(m3u8_index_file_path)
        self.streams: list[StreamVariant] = []
        self._pending: StreamVariant | None = None
        self.selected_stream: StreamVariant | None = None

    def __parse_stream_info(self, line: str):
        if not line.startswith(KEY_EXT_X_STREAM_INF):
            return
        self._pending = StreamVariant()
        stream_info = line.split(KEY_EXT_X_STREAM_INF, 1)[1]
        for info in stream_info.split(','):
            entry = info.split('=', 1)
            if len(entry) < 2:
                continue
            key, value = entry[0], entry[1].strip('"')
            if key == KEY_PROGRAM_ID:
                self._pending.program_id = safe_int(value)
            elif key == KEY_BANDWIDTH:
                self._pending.bandwidth = safe_int(value)
            elif key == KEY_RESOLUTION:
                self._pending.resolution = value

    def __parse_m3u8_ts_info_file(self, line: str):
        line = line.strip()
        if not line.endswith('.m3u8'):
            return
        index_file = self.m3u8_index_file_path.resolve().parent / Path(line)
        variant = self._pending if self._pending else StreamVariant()
        variant.index_file = index_file
        self.streams.append(variant)
        self._pending = None

    def __parse_line(self, index: int, line: str):
        line = line.strip() if line is not None else None
        if line is None:
            return

        self.__parse_stream_info(line)
        self.__parse_m3u8_ts_info_file(line)

    def parse(self):
        file.read_lines(self.m3u8_index_file_path, self.__parse_line)

    def select_stream(self, strategy: str) -> Path | None:
        self.selected_stream = select_stream_variant(self.streams, strategy)
        if self.selected_stream and self.selected_stream.index_file:
            resolution = self.selected_stream.resolution.replace('"', '') or 'unknown'
            print(
                f'selected stream: resolution={resolution} '
                f'bandwidth={self.selected_stream.bandwidth} '
                f'file={self.selected_stream.index_file.name}'
            )
            return self.selected_stream.index_file
        return None

    @property
    def m3u8_ts_info_file(self) -> Path | None:
        if self.selected_stream and self.selected_stream.index_file:
            return self.selected_stream.index_file
        if self.streams:
            return self.streams[-1].index_file
        return None

    def print_stream_info(self):
        print('streams =', len(self.streams))
        for i, stream in enumerate(self.streams):
            print(
                f'  [{i}] resolution={stream.resolution} bandwidth={stream.bandwidth} '
                f'file={stream.index_file}'
            )
        if self.selected_stream:
            print('selected =', self.selected_stream.index_file)


def filter_entry_point_m3u8(m3u8_files: list[Path]) -> list[Path]:
    """过滤被主播放列表引用的子码率 m3u8，只保留需要作为入口处理的文件。"""
    referenced: set[Path] = set()
    for m3u8 in m3u8_files:
        parser = M3U8StreamInfoParser(m3u8)
        parser.parse()
        for stream in parser.streams:
            if stream.index_file:
                referenced.add(stream.index_file.resolve())

    entry_points = sorted(f for f in m3u8_files if f.resolve() not in referenced)
    skipped = len(m3u8_files) - len(entry_points)
    if skipped > 0:
        print(f'skip {skipped} variant m3u8 referenced by master playlist(s)')
    return entry_points

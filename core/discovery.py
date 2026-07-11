"""扫描本地路径，找出可作为入口的 m3u8 文件。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.m3u8_stream import M3U8StreamInfoParser, StreamVariant, filter_entry_point_m3u8


def search_indexs(directory: Path) -> list[Path]:
    all_m3u8 = sorted(directory.rglob('*.m3u8'))
    return filter_entry_point_m3u8(all_m3u8)


def find_entry_m3u8(path: Path) -> list[Path]:
    """从单个文件或目录中找出入口 m3u8 列表。"""
    path = Path(path)
    if path.is_file():
        if path.suffix.lower() != '.m3u8':
            return []
        return filter_entry_point_m3u8([path.resolve()])
    if path.is_dir():
        return search_indexs(path.resolve())
    return []


def find_entry_m3u8_from_paths(paths: list[Path]) -> list[Path]:
    """合并多个路径的扫描结果，按路径去重并排序。"""
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        for m3u8 in find_entry_m3u8(path):
            resolved = m3u8.resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
    return sorted(result)


def default_stream_index(streams: list[StreamVariant]) -> int:
    if not streams:
        return 0
    best = max(streams, key=lambda s: s.bandwidth)
    return streams.index(best)


def format_stream_label(stream: StreamVariant) -> str:
    resolution = stream.resolution.replace('"', '') or '未知分辨率'
    if stream.bandwidth:
        bandwidth = f'{stream.bandwidth // 1000} kbps'
    else:
        bandwidth = '未知码率'
    name = stream.index_file.name if stream.index_file else 'unknown'
    return f'{resolution} ({bandwidth}) — {name}'


@dataclass
class M3u8Entry:
    path: Path
    streams: list[StreamVariant] = field(default_factory=list)
    selected_stream_index: int = 0

    @classmethod
    def from_path(cls, path: Path) -> M3u8Entry:
        parser = M3U8StreamInfoParser(path)
        parser.parse()
        streams = parser.streams
        return cls(
            path=path.resolve(),
            streams=streams,
            selected_stream_index=default_stream_index(streams),
        )

    @property
    def is_master_playlist(self) -> bool:
        return len(self.streams) > 1

    @property
    def stream_labels(self) -> list[str]:
        return [format_stream_label(stream) for stream in self.streams]

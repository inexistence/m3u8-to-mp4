"""输出文件路径解析。"""
import threading
from pathlib import Path

_output_path_lock = threading.Lock()


def resolve_output_directory(output_directory: str | Path | None, source_directory: Path) -> Path:
    """解析输出目录；空值时使用源 m3u8 所在目录。"""
    if output_directory is None or not str(output_directory).strip():
        return source_directory.resolve()

    resolved_directory = Path(output_directory).expanduser().resolve()
    if not resolved_directory.exists():
        raise FileNotFoundError(f'输出目录不存在：{resolved_directory}')
    if not resolved_directory.is_dir():
        raise NotADirectoryError(f'输出路径不是目录：{resolved_directory}')
    return resolved_directory


def resolve_unique_output_path(output_dir: Path, base_name: str, source_m3u8: Path) -> Path:
    """在同目录下选择不冲突的 MP4 输出路径。

    进程内线程安全：通过模块级锁串行化路径分配，避免并行转换竞态。

    命名策略：
    1. 优先使用 base_name（单文件时保持 __DIR_NAME__ / 固定名行为）
    2. 冲突时追加 m3u8 文件名：video_720p.mp4
    3. 仍冲突则追加序号：video_720p_2.mp4

    选定路径后立即 ``touch()`` 占位，供后续并发调用识别为已占用。
    """
    if not base_name.lower().endswith('.mp4'):
        base_name = f'{base_name}.mp4'

    output_dir = output_dir.resolve()
    name_stem = Path(base_name).stem
    source_stem = source_m3u8.resolve().stem

    candidates = [output_dir / base_name]
    if source_stem != name_stem:
        candidates.append(output_dir / f'{name_stem}_{source_stem}.mp4')

    with _output_path_lock:
        for path in candidates:
            if not path.exists():
                path.touch()
                return path

        prefix = f'{name_stem}_{source_stem}' if source_stem != name_stem else name_stem
        for i in range(2, 10000):
            path = output_dir / f'{prefix}_{i}.mp4'
            if not path.exists():
                path.touch()
                return path

        raise RuntimeError(f'无法为 {base_name} 找到可用输出文件名')

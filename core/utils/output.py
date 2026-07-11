"""输出文件路径解析。"""
from pathlib import Path


def resolve_unique_output_path(output_dir: Path, base_name: str, source_m3u8: Path) -> Path:
    """在同目录下选择不冲突的 MP4 输出路径。

    1. 优先使用 base_name（单文件时保持 __DIR_NAME__ / 固定名行为）
    2. 冲突时追加 m3u8 文件名：video_720p.mp4
    3. 仍冲突则追加序号：video_720p_2.mp4
    """
    if not base_name.lower().endswith('.mp4'):
        base_name = f'{base_name}.mp4'

    output_dir = output_dir.resolve()
    name_stem = Path(base_name).stem
    source_stem = source_m3u8.resolve().stem

    candidates = [output_dir / base_name]
    if source_stem != name_stem:
        candidates.append(output_dir / f'{name_stem}_{source_stem}.mp4')

    for path in candidates:
        if not path.exists():
            return path

    prefix = f'{name_stem}_{source_stem}' if source_stem != name_stem else name_stem
    for i in range(2, 10000):
        path = output_dir / f'{prefix}_{i}.mp4'
        if not path.exists():
            return path

    raise RuntimeError(f'无法为 {base_name} 找到可用输出文件名')

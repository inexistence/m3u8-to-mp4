"""转换进度映射。"""
from __future__ import annotations


def map_task_progress(phase: str, current: int, total: int | None) -> tuple[str, int | None, str]:
    """将底层进度映射为对应阶段自身的进度与状态文案。"""
    if phase == 'merging' and total:
        percent = min(100, round(current / total * 100))
        return 'merging', percent, f'正在合片：{percent}%'
    if phase == 'packaging':
        if not total:
            return 'packaging', None, '正在 FFmpeg 封装：进度未知'
        percent = min(100, round(current / total * 100))
        return 'packaging', percent, f'正在 FFmpeg 封装：{percent}%'
    return phase, None, '转换中'

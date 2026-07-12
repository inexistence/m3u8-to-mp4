"""FFmpeg 可执行文件检测。"""
from __future__ import annotations

import subprocess

FFMPEG_DOWNLOAD_URL = 'https://ffmpeg.org/download.html'

_UNSET = object()
_cached_path: str | None | object = _UNSET
# find_ffmpeg 未命中时的原因：missing | unrunnable
_last_failure: str | None = None


def ffmpeg_missing_message() -> str:
    if _last_failure == 'unrunnable':
        return (
            '找到 FFmpeg，但无法运行。\n\n'
            '可能被杀毒软件隔离、文件损坏或缺少执行权限。\n'
            '请检查 imageio-ffmpeg 自带的二进制，或自行安装 FFmpeg：\n'
            f'{FFMPEG_DOWNLOAD_URL}\n\n'
            '可在终端运行 ffmpeg -version 排查。'
        )
    return (
        '未找到 FFmpeg。\n\n'
        '请安装依赖（含 imageio-ffmpeg），或自行安装 FFmpeg 并将 bin 目录加入 PATH：\n'
        f'{FFMPEG_DOWNLOAD_URL}\n\n'
        '安装后在终端运行 ffmpeg -version 验证。'
    )


def _is_runnable(path: str) -> bool:
    try:
        completed = subprocess.run(
            [path, '-version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_ffmpeg() -> str | None:
    """通过 imageio-ffmpeg 解析可用的 ffmpeg，并缓存首次探测结果。

    imageio-ffmpeg 自身会依次尝试：环境变量、自带二进制、conda、系统 PATH。
    """
    global _cached_path, _last_failure
    if _cached_path is not _UNSET:
        return _cached_path  # type: ignore[return-value]

    _last_failure = 'missing'
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        _cached_path = None
        return None

    if _is_runnable(path):
        _cached_path = path
        _last_failure = None
        return path

    _last_failure = 'unrunnable'
    _cached_path = None
    return None


def describe_ffmpeg_status() -> tuple[bool, str]:
    """返回 (是否可用, 状态栏短文案)。"""
    if find_ffmpeg() is not None:
        return True, '● FFmpeg 已就绪'
    if _last_failure == 'unrunnable':
        return False, '● FFmpeg 无法运行'
    return False, '● 未找到 FFmpeg'


def ensure_ffmpeg() -> str:
    """返回 ffmpeg 可执行文件路径；未找到或无法运行时抛出 RuntimeError。"""
    path = find_ffmpeg()
    if path is None:
        raise RuntimeError(ffmpeg_missing_message())
    return path

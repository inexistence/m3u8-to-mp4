"""FFmpeg 可执行文件检测。"""
import shutil

FFMPEG_DOWNLOAD_URL = 'https://ffmpeg.org/download.html'


def ffmpeg_missing_message() -> str:
    return (
        '未在系统 PATH 中找到 FFmpeg。\n\n'
        f'请先安装 FFmpeg 并将 bin 目录加入 PATH：\n{FFMPEG_DOWNLOAD_URL}\n\n'
        '安装后在终端运行 ffmpeg -version 验证。'
    )


def find_ffmpeg() -> str | None:
    return shutil.which('ffmpeg')


def ensure_ffmpeg() -> str:
    """返回 ffmpeg 可执行文件路径；未找到时抛出 RuntimeError。"""
    path = find_ffmpeg()
    if path is None:
        raise RuntimeError(ffmpeg_missing_message())
    return path

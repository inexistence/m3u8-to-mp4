"""通过 FFmpeg 将解密后的 TS 流封装为 MP4。"""
import ffmpeg
from core.merge.ts_merge import TsMerger
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Callable

from tqdm import tqdm

from core.utils.cancellation import ConversionCancelled
from core.utils.ffmpeg_check import ensure_ffmpeg


def parse_ffmpeg_progress_line(line: str) -> int | None:
    """从 FFmpeg machine-readable progress 输出中取出 out_time_ms。"""
    key, separator, value = line.strip().partition('=')
    if key != 'out_time_ms' or not separator:
        return None
    try:
        return int(value)
    except ValueError:
        return None


class FfmpegMerger(TsMerger):
    """将分片流式写入临时 merged.ts，再由 FFmpeg 以 copy 模式封装为 MP4。

    相比逐分片建临时文件，单文件流式写入在大量分片时性能更好，且跨平台兼容。
    """

    def __init__(
        self,
        target_file_path: str | Path,
        progress_callback: Callable[[str, int, int | None], None] | None = None,
        cancel_event: threading.Event | None = None,
    ):
        if isinstance(target_file_path, str):
            self.target_file_path = Path(target_file_path)
        else:
            self.target_file_path = target_file_path
        self.tmp_dir = None
        self.merged_ts_path = None
        self.merged_ts_file = None
        self._pbar: tqdm | None = None
        self._progress_callback = progress_callback
        self._progress_total = 0
        self._progress_current = 0
        self._media_duration_ms: int | None = None
        self._cancel_event = cancel_event
        self._process: subprocess.Popen | None = None

    @staticmethod
    def _can_report_progress() -> bool:
        """窗口程序以无控制台方式启动时，标准流可能为 None。"""
        return getattr(sys.stderr, 'write', None) is not None

    def _raise_if_cancelled(self) -> None:
        if self._cancel_event is not None and self._cancel_event.is_set():
            raise ConversionCancelled()

    def _cleanup_temp(self) -> None:
        if self.merged_ts_file is not None:
            self.merged_ts_file.close()
            self.merged_ts_file = None
        if self.tmp_dir is not None:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = None

    def _remove_incomplete_output(self) -> None:
        try:
            self.target_file_path.unlink(missing_ok=True)
        except OSError:
            pass

    def start(self):
        tmp_dir_name = tempfile.mkdtemp()
        self.tmp_dir = Path(tmp_dir_name)
        self.merged_ts_path = self.tmp_dir / 'merged.ts'
        self.merged_ts_file = open(self.merged_ts_path, 'wb')
        if self._can_report_progress():
            tqdm.write(f'tmp dir {tmp_dir_name}')

    def set_progress_total(self, total: int):
        self._progress_total = total
        self._progress_current = 0
        if self._progress_callback is not None:
            self._progress_callback('merging', 0, total)
        if self._can_report_progress():
            self._pbar = tqdm(total=total, unit='seg', desc='merging', dynamic_ncols=True)

    def append(self, data: bytearray):
        self.merged_ts_file.write(data)
        if self._pbar is not None:
            self._pbar.update(1)
        self._progress_current += 1
        if self._progress_callback is not None and self._progress_total:
            self._progress_callback('merging', self._progress_current, self._progress_total)

    def set_media_duration_ms(self, duration_ms: int | None) -> None:
        self._media_duration_ms = duration_ms if duration_ms and duration_ms > 0 else None

    def _report_packaging_progress(self, current_us: int = 0) -> None:
        if self._progress_callback is None:
            return
        total_us = self._media_duration_ms * 1000 if self._media_duration_ms is not None else None
        self._progress_callback('packaging', current_us, total_us)

    def _run_ffmpeg(self, command: list[str]) -> None:
        self._report_packaging_progress()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        assert process.stdout is not None
        for line in process.stdout:
            out_time_us = parse_ffmpeg_progress_line(line)
            if out_time_us is not None:
                self._report_packaging_progress(out_time_us)
        returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        if self._media_duration_ms is not None:
            self._report_packaging_progress(self._media_duration_ms * 1000)

    def finish(self):
        if self._pbar is not None:
            self._pbar.close()
            self._pbar = None

        if self.merged_ts_file is not None:
            self.merged_ts_file.close()
            self.merged_ts_file = None
            if self._cancel_event is not None and self._cancel_event.is_set():
                self._cleanup_temp()
                self._remove_incomplete_output()
                raise ConversionCancelled()
            if self._can_report_progress():
                tqdm.write('converting to mp4...')
            try:
                stream = (
                    ffmpeg.input(str(self.merged_ts_path))
                    .output(str(self.target_file_path), c='copy')
                    .global_args('-progress', 'pipe:1', '-nostats')
                    .overwrite_output()
                )
                command = stream.compile(cmd=ensure_ffmpeg())
                self._run_ffmpeg(command)
                if self._can_report_progress():
                    tqdm.write(f'merge success, output = {self.target_file_path}')
            finally:
                self._cleanup_temp()
        elif self.tmp_dir is not None:
            self._cleanup_temp()

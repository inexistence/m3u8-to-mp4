"""通过 FFmpeg 将解密后的 TS 流封装为 MP4。"""
import ffmpeg
from core.merge.ts_merge import TsMerger
from pathlib import Path
import subprocess
import sys
import threading
from typing import Callable

from tqdm import tqdm

from core.utils.cancellation import ConversionCancelled
from core.utils.ffmpeg_check import ensure_ffmpeg


class FfmpegMerger(TsMerger):
    """解密后的 TS 分片经管道流式喂给 FFmpeg，以 copy 模式封装为 MP4。

    不落盘中间 merged.ts：start 时启动 ffmpeg，append 写 stdin，finish 关闭管道并等待退出。
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
        self._pbar: tqdm | None = None
        self._progress_callback = progress_callback
        self._progress_total = 0
        self._progress_current = 0
        self._cancel_event = cancel_event
        self._process: subprocess.Popen | None = None
        self._command: list[str] = []

    @staticmethod
    def _can_report_progress() -> bool:
        """窗口程序以无控制台方式启动时，标准流可能为 None。"""
        return getattr(sys.stderr, 'write', None) is not None

    def _raise_if_cancelled(self) -> None:
        if self._cancel_event is not None and self._cancel_event.is_set():
            raise ConversionCancelled()

    def _remove_incomplete_output(self) -> None:
        try:
            self.target_file_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _close_stdin(self) -> None:
        process = self._process
        if process is None or process.stdin is None or process.stdin.closed:
            return
        try:
            process.stdin.close()
        except OSError:
            pass

    def _terminate_process(self) -> None:
        process = self._process
        if process is None:
            return
        self._close_stdin()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def _wait_for_ffmpeg(self, command: list[str]) -> None:
        process = self._process
        if process is None:
            return
        self._raise_if_cancelled()
        returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)

    def start(self):
        self._raise_if_cancelled()
        stream = (
            ffmpeg.input('pipe:0', f='mpegts')
            .output(str(self.target_file_path), c='copy')
            .overwrite_output()
        )
        command = stream.compile(cmd=ensure_ffmpeg())
        if self._can_report_progress():
            tqdm.write('streaming to ffmpeg...')
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        self._process = process
        self._command = command

    def set_progress_total(self, total: int):
        self._progress_total = total
        self._progress_current = 0
        if self._progress_callback is not None:
            self._progress_callback('converting', 0, total)
        if self._can_report_progress():
            self._pbar = tqdm(total=total, unit='seg', desc='converting', dynamic_ncols=True)

    def append(self, data: bytearray):
        self._raise_if_cancelled()
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError('FfmpegMerger.append called before start')
        try:
            process.stdin.write(data)
        except BrokenPipeError as exc:
            returncode = process.wait()
            if returncode:
                raise subprocess.CalledProcessError(returncode, self._command) from exc
            raise
        if self._pbar is not None:
            self._pbar.update(1)
        self._progress_current += 1
        if self._progress_callback is not None and self._progress_total:
            self._progress_callback('converting', self._progress_current, self._progress_total)

    def set_media_duration_ms(self, duration_ms: int | None) -> None:
        """保留接口兼容；流式单阶段进度按分片计数，不再使用时长。"""
        return

    def finish(self):
        if self._pbar is not None:
            self._pbar.close()
            self._pbar = None

        process = self._process
        if process is None:
            return

        command = self._command
        try:
            if self._cancel_event is not None and self._cancel_event.is_set():
                self._terminate_process()
                self._remove_incomplete_output()
                raise ConversionCancelled()

            self._close_stdin()
            try:
                self._wait_for_ffmpeg(command)
            except ConversionCancelled:
                self._terminate_process()
                self._remove_incomplete_output()
                raise
            if self._can_report_progress():
                tqdm.write(f'merge success, output = {self.target_file_path}')
        except ConversionCancelled:
            raise
        except Exception:
            self._terminate_process()
            self._remove_incomplete_output()
            raise
        finally:
            self._process = None

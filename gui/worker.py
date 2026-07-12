"""后台转换线程。"""
from __future__ import annotations

import io
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Callable, Sequence

from core.m3u8converter import M3U8Converter
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus


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


@dataclass
class WorkerEvent:
    kind: str
    message: str = ''
    task_index: int = -1
    done_count: int = 0
    total_count: int = 0
    progress_percent: int | None = None
    progress_phase: str = ''


class ConversionWorker:
    def __init__(
        self,
        tasks: Sequence[ConversionTask],
        config: GlobalConfig,
        on_event: Callable[[WorkerEvent], None],
    ):
        self.tasks = tuple(tasks)
        self.global_config = config
        self.on_event = on_event
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._cancel.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _emit(
        self,
        kind: str,
        message: str = '',
        task_index: int = -1,
        done_count: int = 0,
        total_count: int = 0,
        progress_percent: int | None = None,
        progress_phase: str = '',
    ) -> None:
        self.on_event(WorkerEvent(
            kind=kind,
            message=message,
            task_index=task_index,
            done_count=done_count,
            total_count=total_count,
            progress_percent=progress_percent,
            progress_phase=progress_phase,
        ))

    def _convert_one(self, task: ConversionTask, task_index: int) -> None:
        task.status = TaskStatus.RUNNING
        stream_index = task.selected_stream_index if task.is_master_playlist else None
        buffer = io.StringIO()
        try:
            def report_progress(phase: str, current: int, total: int | None) -> None:
                progress_phase, percent, label = map_task_progress(phase, current, total)
                self._emit(
                    'task_progress',
                    message=label,
                    task_index=task_index,
                    progress_percent=percent,
                    progress_phase=progress_phase,
                )

            with redirect_stdout(buffer), redirect_stderr(buffer):
                converter = M3U8Converter(m3u8_index_file_path=task.path, config=self.global_config)
                converter.convert(
                    stream_index=stream_index,
                    progress_callback=report_progress,
                    cancel_event=self._cancel,
                )
            task.status = TaskStatus.DONE
        except ConversionCancelled as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc) or '用户取消'
            raise
        except Exception as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc)
            buffer.write(traceback.format_exc())
            raise exc
        finally:
            output = buffer.getvalue().strip()
            if output:
                self._emit('log', output)

    def _run(self) -> None:
        batch_tasks = tuple(enumerate(self.tasks))
        total = len(batch_tasks)
        if total == 0:
            self._emit('error', '请至少选择一个文件')
            self._emit('finished')
            return

        self._emit('started', total_count=total)
        done = 0
        for index, task in batch_tasks:
            if self._cancel.is_set():
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.SKIPPED
                continue

            self._emit('task_started', task.path.name, task_index=index, done_count=done, total_count=total)
            try:
                self._convert_one(task, index)
                done += 1
                self._emit('task_done', f'完成: {task.path.name}', task_index=index, done_count=done, total_count=total)
            except Exception as exc:
                self._emit('task_error', f'失败: {task.path.name} — {exc}', task_index=index, done_count=done, total_count=total)

        self._emit('finished', done_count=done, total_count=total)

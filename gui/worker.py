"""后台转换线程。"""
from __future__ import annotations

import io
import threading
import traceback
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Callable

from core.m3u8converter import M3U8Converter
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus


@dataclass
class WorkerEvent:
    kind: str
    message: str = ''
    task_index: int = -1
    done_count: int = 0
    total_count: int = 0


class ConversionWorker:
    def __init__(
        self,
        tasks: list[ConversionTask],
        config: GlobalConfig,
        on_event: Callable[[WorkerEvent], None],
    ):
        self.tasks = tasks
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

    def _emit(self, kind: str, message: str = '', task_index: int = -1, done_count: int = 0, total_count: int = 0) -> None:
        self.on_event(WorkerEvent(
            kind=kind,
            message=message,
            task_index=task_index,
            done_count=done_count,
            total_count=total_count,
        ))

    def _convert_one(self, task: ConversionTask) -> None:
        task.status = TaskStatus.RUNNING
        stream_index = task.selected_stream_index if task.is_master_playlist else None
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                converter = M3U8Converter(m3u8_index_file_path=task.path, config=self.global_config)
                converter.convert(stream_index=stream_index)
            task.status = TaskStatus.DONE
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
        selected_tasks = [(i, task) for i, task in enumerate(self.tasks) if task.selected]
        total = len(selected_tasks)
        if total == 0:
            self._emit('error', '请至少选择一个文件')
            self._emit('finished')
            return

        self._emit('started', total_count=total)
        done = 0
        for index, task in selected_tasks:
            if self._cancel.is_set():
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.SKIPPED
                continue

            self._emit('task_started', task.path.name, task_index=index, done_count=done, total_count=total)
            try:
                self._convert_one(task)
                done += 1
                self._emit('task_done', f'完成: {task.path.name}', task_index=index, done_count=done, total_count=total)
            except Exception as exc:
                self._emit('task_error', f'失败: {task.path.name} — {exc}', task_index=index, done_count=done, total_count=total)

        self._emit('finished', done_count=done, total_count=total)

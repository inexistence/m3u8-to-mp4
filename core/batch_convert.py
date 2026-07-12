"""批量并行转换。"""
from __future__ import annotations

import io
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Callable, Sequence

from core.m3u8converter import M3U8Converter
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig, normalize_max_parallel_conversions
from gui.models import ConversionTask, TaskStatus


@dataclass
class BatchCancelController:
    batch_cancel: threading.Event = field(default_factory=threading.Event)
    task_cancels: list[threading.Event] = field(default_factory=list)

    @classmethod
    def for_tasks(cls, count: int) -> BatchCancelController:
        return cls(task_cancels=[threading.Event() for _ in range(count)])

    def cancel_all(self) -> None:
        self.batch_cancel.set()
        for event in self.task_cancels:
            event.set()

    def cancel_task(self, index: int) -> None:
        if 0 <= index < len(self.task_cancels):
            self.task_cancels[index].set()


@dataclass
class BatchCallbacks:
    on_task_started: Callable[[int, ConversionTask], None] | None = None
    on_task_progress: Callable[[int, str, int, int | None], None] | None = None
    on_task_done: Callable[[int, ConversionTask], None] | None = None
    on_task_error: Callable[[int, ConversionTask, BaseException], None] | None = None
    on_log: Callable[[str], None] | None = None


def resolve_worker_count(config: GlobalConfig) -> int:
    return normalize_max_parallel_conversions(getattr(config, 'max_parallel_conversions', 2))


def run_batch_conversions(
    tasks: Sequence[ConversionTask],
    config: GlobalConfig,
    *,
    cancel: BatchCancelController,
    callbacks: BatchCallbacks | None = None,
) -> int:
    """并行转换；返回成功完成的任务数。"""
    callbacks = callbacks or BatchCallbacks()
    if len(tasks) == 0:
        return 0
    if len(cancel.task_cancels) != len(tasks):
        raise ValueError('cancel.task_cancels length must match tasks')

    workers = resolve_worker_count(config)
    done_lock = threading.Lock()
    done_count = 0

    def convert_one(index: int, task: ConversionTask) -> None:
        nonlocal done_count
        if cancel.batch_cancel.is_set() or cancel.task_cancels[index].is_set():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
            return

        task.status = TaskStatus.RUNNING
        if callbacks.on_task_started:
            callbacks.on_task_started(index, task)

        stream_index = task.selected_stream_index if task.is_master_playlist else None
        buffer = io.StringIO()
        cancel_event = cancel.task_cancels[index]

        def report_progress(phase: str, current: int, total_parts: int | None) -> None:
            if callbacks.on_task_progress:
                callbacks.on_task_progress(index, phase, current, total_parts)

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                converter = M3U8Converter(m3u8_index_file_path=task.path, config=config)
                converter.convert(
                    stream_index=stream_index,
                    progress_callback=report_progress,
                    cancel_event=cancel_event,
                )
            task.status = TaskStatus.DONE
            with done_lock:
                done_count += 1
            if callbacks.on_task_done:
                callbacks.on_task_done(index, task)
        except ConversionCancelled as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc) or '用户取消'
            if callbacks.on_task_error:
                callbacks.on_task_error(index, task, exc)
        except Exception as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc)
            buffer.write(traceback.format_exc())
            if callbacks.on_task_error:
                callbacks.on_task_error(index, task, exc)
        finally:
            output = buffer.getvalue().strip()
            if output and callbacks.on_log:
                callbacks.on_log(output)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(convert_one, index, task) for index, task in enumerate(tasks)]
        for future in as_completed(futures):
            future.result()

    for index, task in enumerate(tasks):
        if task.status == TaskStatus.PENDING and (
            cancel.batch_cancel.is_set() or cancel.task_cancels[index].is_set()
        ):
            task.status = TaskStatus.SKIPPED

    return done_count

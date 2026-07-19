"""后台转换线程（无测试与批处理事件桥接）。"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Sequence

from core.batch_convert import BatchCallbacks, BatchCancelController, run_batch_conversions
from core.models import ConversionTask
from core.progress import map_task_progress
from core.utils.config import GlobalConfig


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
        self._cancel = BatchCancelController.for_tasks(len(self.tasks))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._cancel = BatchCancelController.for_tasks(len(self.tasks))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.cancel_all()

    def cancel_task(self, index: int) -> None:
        self._cancel.cancel_task(index)

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

    def _run(self) -> None:
        total = len(self.tasks)
        if total == 0:
            self._emit('error', '请至少选择一个文件')
            self._emit('finished')
            return

        self._emit('started', total_count=total)
        done_lock = threading.Lock()
        emitted_done = 0

        def current_done() -> int:
            with done_lock:
                return emitted_done

        def on_task_started(index: int, task: ConversionTask) -> None:
            self._emit(
                'task_started',
                task.path.name,
                task_index=index,
                done_count=current_done(),
                total_count=total,
            )

        def on_task_progress(index: int, phase: str, current: int, count: int | None) -> None:
            progress_phase, percent, label = map_task_progress(phase, current, count)
            self._emit(
                'task_progress',
                message=label,
                task_index=index,
                progress_percent=percent,
                progress_phase=progress_phase,
            )

        def on_task_done(index: int, task: ConversionTask) -> None:
            nonlocal emitted_done
            with done_lock:
                emitted_done += 1
                done_count = emitted_done
            self._emit(
                'task_done',
                f'完成: {task.path.name}',
                task_index=index,
                done_count=done_count,
                total_count=total,
            )

        def on_task_error(index: int, task: ConversionTask, exc: BaseException) -> None:
            self._emit(
                'task_error',
                f'失败: {task.path.name} — {exc}',
                task_index=index,
                done_count=current_done(),
                total_count=total,
            )

        callbacks = BatchCallbacks(
            on_task_started=on_task_started,
            on_task_progress=on_task_progress,
            on_task_done=on_task_done,
            on_task_error=on_task_error,
            on_log=lambda output: self._emit('log', output),
        )
        done = run_batch_conversions(
            self.tasks,
            self.global_config,
            cancel=self._cancel,
            callbacks=callbacks,
        )
        self._emit('finished', done_count=done, total_count=total)

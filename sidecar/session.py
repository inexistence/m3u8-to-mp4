from __future__ import annotations

import copy
import threading
from pathlib import Path

from core.batch_convert import BatchCallbacks, BatchCancelController, run_batch_conversions
from core.discovery import M3u8Entry, find_entry_m3u8_from_paths
from core.models import ConversionTask, TaskStatus
from core.queue_messages import scan_feedback
from core.utils.config import GlobalConfig, get_global_config, save_local_config
from core.utils.ffmpeg_check import describe_ffmpeg_status
from gui.worker import map_task_progress
from sidecar.events import EventBus
from sidecar.schemas import ConvertTaskIn, EntryOut, ScanResult


class SidecarSession:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.global_config: GlobalConfig = get_global_config()
        self._is_converting = False
        self._cancel: BatchCancelController | None = None
        self._batch: list[tuple[str, ConversionTask]] = []
        self._thread: threading.Thread | None = None
        self._task_progress: list[dict] = []
        self._lock = threading.RLock()

    def scan(self, paths: list[str], known_paths: list[str]) -> ScanResult:
        known = {Path(path).resolve() for path in known_paths}
        entries: list[EntryOut] = []
        duplicates = 0
        unparseable = 0

        for path in find_entry_m3u8_from_paths([Path(path) for path in paths]):
            resolved = path.resolve()
            if resolved in known:
                duplicates += 1
                continue
            try:
                entry = M3u8Entry.from_path(resolved)
            except Exception:
                unparseable += 1
                continue
            known.add(resolved)
            entries.append(EntryOut(
                path=str(entry.path),
                is_master_playlist=entry.is_master_playlist,
                stream_labels=entry.stream_labels,
                selected_stream_index=entry.selected_stream_index,
            ))

        added = len(entries)
        return ScanResult(
            entries=entries,
            added=added,
            duplicates=duplicates,
            unparseable=unparseable,
            message=scan_feedback(added, duplicates, unparseable, len(known)),
        )

    def get_config(self) -> dict:
        with self._lock:
            return self.global_config.to_local_dict()

    def put_config(self, data: dict) -> dict:
        with self._lock:
            if self._is_converting:
                raise RuntimeError('cannot update config while converting')
            self.global_config.apply_local_dict(data)
            save_local_config(self.global_config)
            return self.global_config.to_local_dict()

    def ffmpeg_status(self) -> dict:
        available, message = describe_ffmpeg_status()
        return {'available': available, 'message': message}

    def start_convert(self, tasks: list[ConvertTaskIn]) -> None:
        with self._lock:
            if self._is_converting:
                raise RuntimeError('conversion already running')
            if not tasks:
                raise ValueError('task list must not be empty')

            task_ids = [item.task_id for item in tasks]
            if len(task_ids) != len(set(task_ids)):
                raise ValueError('duplicate task_id in conversion request')

            batch: list[tuple[str, ConversionTask]] = []
            for item in tasks:
                entry = M3u8Entry.from_path(Path(item.path))
                entry.selected_stream_index = item.selected_stream_index
                batch.append((item.task_id, ConversionTask(entry=entry)))

            batch_config = copy.deepcopy(self.global_config)
            self._batch = batch
            self._task_progress = [
                {'progress_percent': None, 'progress_phase': '', 'message': ''}
                for _ in batch
            ]
            self._cancel = BatchCancelController.for_tasks(len(batch))
            self._is_converting = True
            self._thread = threading.Thread(
                target=self._run_batch,
                args=(batch_config,),
                daemon=True,
            )
            self._thread.start()

    def cancel_all(self) -> None:
        with self._lock:
            cancel = self._cancel
        if cancel is not None:
            cancel.cancel_all()

    def cancel_task(self, task_id: str) -> None:
        with self._lock:
            cancel = self._cancel
            index = next(
                (index for index, (current_id, _) in enumerate(self._batch) if current_id == task_id),
                None,
            )
        if cancel is not None and index is not None:
            cancel.cancel_task(index)

    def batch_snapshot(self) -> dict:
        with self._lock:
            tasks = []
            for index, (task_id, task) in enumerate(self._batch):
                progress = self._task_progress[index]
                tasks.append({
                    'task_id': task_id,
                    'status': task.status.value,
                    'error_message': task.error_message,
                    'progress_percent': progress['progress_percent'],
                    'progress_phase': progress['progress_phase'],
                    'message': progress['message'],
                })
            return {'is_converting': self._is_converting, 'tasks': tasks}

    def _event(
        self,
        event_type: str,
        *,
        index: int | None = None,
        message: str = '',
        done_count: int = 0,
        progress_percent: int | None = None,
        progress_phase: str = '',
        status: TaskStatus | None = None,
        error_message: str = '',
    ) -> dict:
        return {
            'type': event_type,
            'task_id': self._batch[index][0] if index is not None else '',
            'message': message,
            'done_count': done_count,
            'total_count': len(self._batch),
            'progress_percent': progress_percent,
            'progress_phase': progress_phase,
            'status': status.value if status is not None else '',
            'error_message': error_message,
        }

    def _run_batch(self, batch_config: GlobalConfig) -> None:
        with self._lock:
            batch = list(self._batch)
            cancel = self._cancel
        if cancel is None:
            return

        done_count = 0
        done_lock = threading.Lock()

        def terminal_count() -> int:
            with done_lock:
                return done_count

        def advance_terminal() -> int:
            nonlocal done_count
            with done_lock:
                done_count += 1
                return done_count

        def publish_batch_progress(count: int) -> None:
            self.bus.publish(self._event('batch_progress', done_count=count))

        def on_task_started(index: int, task: ConversionTask) -> None:
            message = task.path.name
            with self._lock:
                self._task_progress[index]['message'] = message
            self.bus.publish(self._event(
                'task_started',
                index=index,
                message=message,
                done_count=terminal_count(),
                status=task.status,
            ))

        def on_task_progress(index: int, phase: str, current: int, total: int | None) -> None:
            progress_phase, percent, message = map_task_progress(phase, current, total)
            with self._lock:
                self._task_progress[index].update({
                    'progress_percent': percent,
                    'progress_phase': progress_phase,
                    'message': message,
                })
            self.bus.publish(self._event(
                'task_progress',
                index=index,
                message=message,
                done_count=terminal_count(),
                progress_percent=percent,
                progress_phase=progress_phase,
                status=self._batch[index][1].status,
            ))

        def on_task_done(index: int, task: ConversionTask) -> None:
            count = advance_terminal()
            message = f'完成: {task.path.name}'
            with self._lock:
                self._task_progress[index].update({
                    'progress_percent': 100,
                    'message': message,
                })
            self.bus.publish(self._event(
                'task_done',
                index=index,
                message=message,
                done_count=count,
                progress_percent=100,
                progress_phase=self._task_progress[index]['progress_phase'],
                status=task.status,
            ))
            publish_batch_progress(count)

        def on_task_error(index: int, task: ConversionTask, exc: BaseException) -> None:
            count = advance_terminal()
            message = f'失败: {task.path.name} — {exc}'
            with self._lock:
                self._task_progress[index]['message'] = message
            self.bus.publish(self._event(
                'task_error',
                index=index,
                message=message,
                done_count=count,
                progress_percent=self._task_progress[index]['progress_percent'],
                progress_phase=self._task_progress[index]['progress_phase'],
                status=task.status,
                error_message=task.error_message,
            ))
            publish_batch_progress(count)

        callbacks = BatchCallbacks(
            on_task_started=on_task_started,
            on_task_progress=on_task_progress,
            on_task_done=on_task_done,
            on_task_error=on_task_error,
        )

        batch_error = ''
        try:
            run_batch_conversions(
                [task for _, task in batch],
                batch_config,
                cancel=cancel,
                callbacks=callbacks,
            )
        except Exception as exc:
            batch_error = str(exc)
        finally:
            for index, (_, task) in enumerate(batch):
                if task.status != TaskStatus.SKIPPED:
                    continue
                count = advance_terminal()
                message = f'已跳过: {task.path.name}'
                with self._lock:
                    self._task_progress[index]['message'] = message
                self.bus.publish(self._event(
                    'task_skipped',
                    index=index,
                    message=message,
                    done_count=count,
                    status=task.status,
                ))
                publish_batch_progress(count)

            with self._lock:
                finished_event = self._event(
                    'batch_finished',
                    message=batch_error,
                    done_count=terminal_count(),
                    error_message=batch_error,
                )
                self._is_converting = False
            self.bus.publish(finished_event)

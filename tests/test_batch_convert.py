from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.batch_convert import BatchCancelController, run_batch_conversions
from core.discovery import M3u8Entry
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus


def _task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class BatchConvertTests(unittest.TestCase):
    def test_respects_max_parallel(self) -> None:
        tasks = [_task(f'{i}.m3u8') for i in range(4)]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        current = 0
        peak = 0
        lock = threading.Lock()

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            nonlocal current, peak
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.05)
            with lock:
                current -= 1

        cancel = BatchCancelController.for_tasks(len(tasks))
        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            done = run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(done, 4)
        self.assertLessEqual(peak, 2)
        self.assertTrue(all(t.status == TaskStatus.DONE for t in tasks))

    def test_cancel_all_marks_running_error_and_pending_skipped(self) -> None:
        tasks = [_task('a.m3u8'), _task('b.m3u8'), _task('c.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        cancel = BatchCancelController.for_tasks(len(tasks))
        started = threading.Event()

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            started.set()
            while not cancel_event.is_set():
                time.sleep(0.01)
            raise ConversionCancelled()

        def trigger():
            started.wait(timeout=2)
            cancel.cancel_all()

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            threading.Thread(target=trigger, daemon=True).start()
            run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(tasks[0].status, TaskStatus.ERROR)
        self.assertEqual(tasks[0].error_message, '用户取消')
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        self.assertEqual(tasks[2].status, TaskStatus.SKIPPED)

    def test_cancel_pending_skips_without_convert(self) -> None:
        tasks = [_task('a.m3u8'), _task('b.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        cancel = BatchCancelController.for_tasks(len(tasks))
        cancel.cancel_task(1)
        calls = []

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            calls.append(cancel_event)

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            done = run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(done, 1)
        self.assertEqual(tasks[0].status, TaskStatus.DONE)
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        self.assertEqual(len(calls), 1)

    def test_cancel_running_task_only_affects_that_task(self) -> None:
        tasks = [_task('a.m3u8'), _task('b.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        cancel = BatchCancelController.for_tasks(len(tasks))
        started = [threading.Event(), threading.Event()]

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            if cancel_event is cancel.task_cancels[0]:
                started[0].set()
                started[1].wait(timeout=2)
                while not cancel_event.is_set():
                    time.sleep(0.01)
                raise ConversionCancelled()
            started[1].set()
            started[0].wait(timeout=2)
            time.sleep(0.02)

        def trigger():
            started[0].wait(timeout=2)
            started[1].wait(timeout=2)
            cancel.cancel_task(0)

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            threading.Thread(target=trigger, daemon=True).start()
            done = run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(done, 1)
        self.assertEqual(tasks[0].status, TaskStatus.ERROR)
        self.assertEqual(tasks[0].error_message, '用户取消')
        self.assertEqual(tasks[1].status, TaskStatus.DONE)


if __name__ == '__main__':
    unittest.main()

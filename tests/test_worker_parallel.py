from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.discovery import M3u8Entry
from core.utils.config import GlobalConfig
from core.conversion_worker import ConversionWorker, WorkerEvent
from core.models import ConversionTask, TaskStatus


def _make_task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class WorkerParallelTests(unittest.TestCase):
    def test_cancel_task_skips_pending_only(self) -> None:
        tasks = [_make_task('a.m3u8'), _make_task('b.m3u8'), _make_task('c.m3u8')]
        events: list[WorkerEvent] = []
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        worker = ConversionWorker(tasks, config, events.append)
        worker.cancel_task(1)
        calls: list[threading.Event] = []

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            calls.append(cancel_event)

        with patch('core.batch_convert.M3U8Converter') as converter_cls:
            converter_cls.return_value.convert.side_effect = fake_convert
            worker._run()

        self.assertEqual(tasks[0].status, TaskStatus.DONE)
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        self.assertEqual(tasks[2].status, TaskStatus.DONE)
        self.assertEqual(len(calls), 2)

        task_done_events = [event for event in events if event.kind == 'task_done']
        finished = next(event for event in events if event.kind == 'finished')
        self.assertEqual(len(task_done_events), 2)
        self.assertEqual(finished.done_count, 2)
        self.assertEqual(finished.total_count, 3)

    def test_parallel_peak_at_most_two(self) -> None:
        tasks = [_make_task(f'{index}.m3u8') for index in range(4)]
        events: list[WorkerEvent] = []
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        worker = ConversionWorker(tasks, config, events.append)
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

        with patch('core.batch_convert.M3U8Converter') as converter_cls:
            converter_cls.return_value.convert.side_effect = fake_convert
            worker._run()

        self.assertEqual(peak, 2)
        self.assertTrue(all(task.status == TaskStatus.DONE for task in tasks))
        finished = next(event for event in events if event.kind == 'finished')
        self.assertEqual(finished.done_count, 4)
        self.assertEqual(finished.total_count, 4)


if __name__ == '__main__':
    unittest.main()

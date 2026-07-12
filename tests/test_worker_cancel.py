from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.discovery import M3u8Entry
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus
from gui.worker import ConversionWorker, WorkerEvent


def _make_task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class WorkerCancelTests(unittest.TestCase):
    def test_cancelled_task_becomes_error_and_pending_skipped(self) -> None:
        task_a = _make_task('a.m3u8')
        task_b = _make_task('b.m3u8')
        events: list[WorkerEvent] = []
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        worker = ConversionWorker([task_a, task_b], config, events.append)
        seen_cancel_event = []

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            seen_cancel_event.append(cancel_event)
            worker.cancel()
            deadline = time.time() + 2
            while not cancel_event.is_set() and time.time() < deadline:
                time.sleep(0.01)
            raise ConversionCancelled()

        with patch('core.batch_convert.M3U8Converter') as converter_cls:
            converter_cls.return_value.convert.side_effect = fake_convert
            worker._run()

        self.assertEqual(task_a.status, TaskStatus.ERROR)
        self.assertEqual(task_a.error_message, '用户取消')
        self.assertEqual(task_b.status, TaskStatus.SKIPPED)

        kinds = [e.kind for e in events]
        self.assertIn('task_error', kinds)
        self.assertIn('finished', kinds)

        task_error = next(e for e in events if e.kind == 'task_error')
        finished = next(e for e in events if e.kind == 'finished')
        self.assertEqual(task_error.done_count, 0)
        self.assertEqual(finished.done_count, 0)
        self.assertNotIn('task_done', kinds)

        self.assertEqual(len(seen_cancel_event), 1)
        self.assertIsInstance(seen_cancel_event[0], threading.Event)
        self.assertTrue(seen_cancel_event[0].is_set())
        converter_cls.return_value.convert.assert_called_once()


if __name__ == '__main__':
    unittest.main()

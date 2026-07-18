from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from sidecar.session import SidecarSession
from sidecar.schemas import ConvertTaskIn


class SidecarSessionTests(unittest.TestCase):
    def test_scan_dedupes_against_known_paths(self) -> None:
        session = SidecarSession()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'index.m3u8'
            target.write_text('#EXTM3U\n#EXTINF:1,\nseg.ts\n', encoding='utf-8')
            (root / 'seg.ts').write_bytes(b'\x00')
            first = session.scan([str(root)], known_paths=[])
            self.assertEqual(first.added, 1)
            second = session.scan([str(root)], known_paths=[str(target.resolve())])
            self.assertEqual(second.added, 0)
            self.assertEqual(second.duplicates, 1)

    def test_batch_snapshot_idle(self) -> None:
        session = SidecarSession()
        snap = session.batch_snapshot()
        self.assertFalse(snap['is_converting'])
        self.assertEqual(snap['tasks'], [])

    def test_start_convert_rejects_duplicate_task_ids(self) -> None:
        session = SidecarSession()
        tasks = [
            ConvertTaskIn(task_id='duplicate', path='first.m3u8'),
            ConvertTaskIn(task_id='duplicate', path='second.m3u8'),
        ]

        with self.assertRaisesRegex(ValueError, 'duplicate task_id'):
            session.start_convert(tasks)

    def test_start_convert_rejects_empty_task_list(self) -> None:
        session = SidecarSession()

        with self.assertRaisesRegex(ValueError, 'task list must not be empty'):
            session.start_convert([])

    def test_batch_uses_config_snapshot_and_rejects_updates_while_running(self) -> None:
        session = SidecarSession()
        started = threading.Event()
        release = threading.Event()
        captured_config = []

        def hold_batch(tasks, config, *, cancel, callbacks):
            captured_config.append(config)
            started.set()
            self.assertTrue(release.wait(timeout=2))
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'index.m3u8'
            path.write_text('#EXTM3U\n#EXTINF:1,\nseg.ts\n', encoding='utf-8')
            task = ConvertTaskIn(task_id='task-1', path=str(path))

            with patch('sidecar.session.run_batch_conversions', side_effect=hold_batch):
                session.start_convert([task])
                self.assertTrue(started.wait(timeout=2))
                try:
                    with self.assertRaisesRegex(RuntimeError, 'cannot update config while converting'):
                        session.put_config({'output_file_name': 'future.mp4'})
                    self.assertEqual(len(captured_config), 1)
                    self.assertIsNot(captured_config[0], session.global_config)
                    self.assertEqual(
                        captured_config[0].to_local_dict(),
                        session.global_config.to_local_dict(),
                    )
                finally:
                    release.set()
                    session._thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidecar.session import SidecarSession


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


if __name__ == '__main__':
    unittest.main()

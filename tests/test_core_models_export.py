# tests/test_core_models_export.py
from __future__ import annotations

import unittest
from pathlib import Path

from core.discovery import M3u8Entry
from core.models import ConversionTask, TaskStatus


class CoreModelsExportTests(unittest.TestCase):
    def test_task_defaults(self) -> None:
        task = ConversionTask(entry=M3u8Entry(path=Path('a.m3u8')))
        self.assertTrue(task.selected)
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.error_message, '')
        self.assertEqual(task.path, Path('a.m3u8').resolve() if Path('a.m3u8').exists() else task.entry.path)


if __name__ == '__main__':
    unittest.main()

"""FfmpegMerger 封装行为测试。"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.merge.ffmpeg_merge import FfmpegMerger


class FfmpegMergerOverwriteTests(unittest.TestCase):
    def test_finish_passes_overwrite_and_devnull_stdin(self) -> None:
        """无控制台 GUI 下必须 -y 且关闭 stdin，避免覆盖确认挂起。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            mock_proc = MagicMock()
            mock_proc.stdout = iter([])
            mock_proc.wait.return_value = 0

            with (
                patch('core.merge.ffmpeg_merge.ensure_ffmpeg', return_value='ffmpeg'),
                patch('core.merge.ffmpeg_merge.subprocess.Popen', return_value=mock_proc) as popen,
            ):
                merger = FfmpegMerger(target)
                merger.start()
                merger.append(bytearray(b'\x00' * 16))
                merger.finish()

            popen.assert_called_once()
            command = popen.call_args.args[0]
            kwargs = popen.call_args.kwargs
            self.assertIn('-y', command)
            self.assertIs(kwargs.get('stdin'), subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()

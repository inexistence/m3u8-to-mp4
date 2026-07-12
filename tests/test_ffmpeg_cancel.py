from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.merge.ffmpeg_merge import FfmpegMerger
from core.utils.cancellation import ConversionCancelled


class FfmpegMergerCancelFinishTests(unittest.TestCase):
    def test_finish_raises_and_skips_ffmpeg_when_cancelled(self) -> None:
        cancel = threading.Event()
        cancel.set()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            with patch('core.merge.ffmpeg_merge.ensure_ffmpeg') as ensure:
                merger = FfmpegMerger(target, cancel_event=cancel)
                merger.start()
                tmp_dir = merger.tmp_dir
                merger.append(bytearray(b'\x00' * 8))
                with self.assertRaises(ConversionCancelled):
                    merger.finish()
                ensure.assert_not_called()
                self.assertFalse(tmp_dir.exists())
                self.assertFalse(target.exists())


class FfmpegMergerCancelProcessTests(unittest.TestCase):
    def test_run_ffmpeg_terminates_process_when_cancelled(self) -> None:
        cancel = threading.Event()
        cancel.set()
        mock_proc = MagicMock()
        mock_proc.stdout = iter(['out_time_ms=1000\n', 'out_time_ms=2000\n'])
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = 1

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            target.write_bytes(b'partial')
            merger = FfmpegMerger(target, cancel_event=cancel)
            with patch('core.merge.ffmpeg_merge.subprocess.Popen', return_value=mock_proc):
                with self.assertRaises(ConversionCancelled):
                    merger._run_ffmpeg(['ffmpeg', '-y', '-i', 'in.ts', str(target)])
            mock_proc.terminate.assert_called()
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

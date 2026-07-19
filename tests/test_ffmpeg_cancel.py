from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.merge.ffmpeg_merge import FfmpegMerger
from core.utils.cancellation import ConversionCancelled


def _mock_ffmpeg_process(*, poll_value=None, wait_value=1):
    mock_stdin = MagicMock()
    mock_stdin.closed = False
    mock_proc = MagicMock()
    mock_proc.stdin = mock_stdin
    mock_proc.poll.return_value = poll_value
    mock_proc.wait.return_value = wait_value
    return mock_proc


class FfmpegMergerCancelFinishTests(unittest.TestCase):
    def test_finish_raises_and_terminates_when_cancelled(self) -> None:
        cancel = threading.Event()
        mock_proc = _mock_ffmpeg_process(poll_value=None, wait_value=1)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            with (
                patch('core.merge.ffmpeg_merge.ensure_ffmpeg', return_value='ffmpeg'),
                patch('core.merge.ffmpeg_merge.subprocess.Popen', return_value=mock_proc),
            ):
                merger = FfmpegMerger(target, cancel_event=cancel)
                merger.start()
                merger.append(bytearray(b'\x00' * 8))
                cancel.set()
                with self.assertRaises(ConversionCancelled):
                    merger.finish()
            mock_proc.terminate.assert_called()
            self.assertFalse(target.exists())


class FfmpegMergerCancelProcessTests(unittest.TestCase):
    def test_wait_terminates_process_when_cancelled(self) -> None:
        cancel = threading.Event()
        mock_proc = _mock_ffmpeg_process(poll_value=None, wait_value=1)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            target.write_bytes(b'partial')
            with (
                patch('core.merge.ffmpeg_merge.ensure_ffmpeg', return_value='ffmpeg'),
                patch('core.merge.ffmpeg_merge.subprocess.Popen', return_value=mock_proc),
            ):
                merger = FfmpegMerger(target, cancel_event=cancel)
                merger.start()
                cancel.set()
                with self.assertRaises(ConversionCancelled):
                    merger.finish()
            mock_proc.terminate.assert_called()
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

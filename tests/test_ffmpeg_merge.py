"""FfmpegMerger 封装行为测试。"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.merge.ffmpeg_merge import FfmpegMerger


class FfmpegMergerPipeTests(unittest.TestCase):
    def test_start_uses_pipe_stdin_and_overwrite(self) -> None:
        """流式模式下 stdin 为 PIPE，命令含 -y 与 pipe 输入，避免覆盖确认挂起。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            mock_stdin = MagicMock()
            mock_stdin.closed = False
            mock_proc = MagicMock()
            mock_proc.stdin = mock_stdin
            mock_proc.wait.return_value = 0
            mock_proc.poll.return_value = 0

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
            self.assertTrue(any(arg in {'pipe:0', 'pipe:'} for arg in command))
            self.assertIs(kwargs.get('stdin'), subprocess.PIPE)
            self.assertIs(kwargs.get('stdout'), subprocess.DEVNULL)
            mock_stdin.write.assert_called_once_with(bytearray(b'\x00' * 16))
            mock_stdin.close.assert_called()


if __name__ == '__main__':
    unittest.main()

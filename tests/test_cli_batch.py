from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.utils.config import GlobalConfig
import main as cli_main


class CliBatchTests(unittest.TestCase):
    def test_directory_uses_run_batch_conversions(self) -> None:
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        paths = [Path('a.m3u8'), Path('b.m3u8')]

        with patch('main.get_global_config', return_value=config), \
             patch('main.ensure_ffmpeg'), \
             patch('main.find_entry_m3u8', return_value=paths), \
             patch('main.run_batch_conversions', return_value=2) as run_batch, \
             patch('main.os.path.isfile', return_value=False), \
             patch('main.os.path.isdir', return_value=True):
            cli_main.main(Path('some_dir'))

        run_batch.assert_called_once()
        args, kwargs = run_batch.call_args
        self.assertEqual(len(args[0]), 2)
        self.assertIs(args[1], config)


if __name__ == '__main__':
    unittest.main()

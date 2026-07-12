from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.m3u8converter import M3U8Converter
from core.utils.config import GlobalConfig


class ConverterCancelWiringTests(unittest.TestCase):
    def test_convert_passes_cancel_event_to_merger_and_parser(self) -> None:
        cancel = threading.Event()
        config = MagicMock(spec=GlobalConfig)
        config.output_directory = None
        config.output_file_name = 'out'
        config.stream_selection = 'highest_bandwidth'
        config.aes_iv_mode = 'auto'
        config.skip_first_part = False
        config.reset_decryption_if_part_changed = False

        fake_path = Path(__file__)
        converter = M3U8Converter(fake_path, config)
        merger_init = MagicMock()
        parser_init = MagicMock()
        parser_instance = MagicMock()
        parser_instance.get_total_duration_ms.return_value = None
        parser_init.return_value = parser_instance

        with (
            patch('core.m3u8converter.ensure_ffmpeg'),
            patch.object(converter.m3u8_stream_info_parser, 'parse'),
            patch.object(converter.m3u8_stream_info_parser, 'streams', []),
            patch('core.m3u8converter.resolve_unique_output_path', return_value=fake_path.with_suffix('.mp4')),
            patch('core.m3u8converter.FfmpegMerger', merger_init) as merger_cls,
            patch('core.m3u8converter.SimpleM3U8TsParser', parser_init),
        ):
            merger_cls.return_value = MagicMock()
            converter.convert(cancel_event=cancel)

        self.assertEqual(merger_init.call_args.kwargs.get('cancel_event'), cancel)
        self.assertEqual(parser_init.call_args.kwargs.get('cancel_event'), cancel)


if __name__ == '__main__':
    unittest.main()

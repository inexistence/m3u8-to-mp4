from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from core.m3u8_ts_parser import SimpleM3U8TsParser
from core.utils.cancellation import ConversionCancelled


class ParserCancelTests(unittest.TestCase):
    def test_raise_if_cancelled(self) -> None:
        cancel = threading.Event()
        cancel.set()
        parser = SimpleM3U8TsParser(__file__, MagicMock(), cancel_event=cancel)
        with self.assertRaises(ConversionCancelled):
            parser._raise_if_cancelled()

    def test_handle_ts_line_checks_cancel_before_read(self) -> None:
        cancel = threading.Event()
        cancel.set()
        merger = MagicMock()
        parser = SimpleM3U8TsParser(__file__, merger, cancel_event=cancel)
        with self.assertRaises(ConversionCancelled):
            parser._SimpleM3U8TsParser__handle_line(0, 'seg001.ts')
        merger.append.assert_not_called()


if __name__ == '__main__':
    unittest.main()

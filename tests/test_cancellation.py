from __future__ import annotations

import unittest

from core.utils.cancellation import ConversionCancelled


class ConversionCancelledTests(unittest.TestCase):
    def test_is_exception_with_default_message(self) -> None:
        exc = ConversionCancelled()
        self.assertIsInstance(exc, Exception)
        self.assertEqual(str(exc), '用户取消')


if __name__ == '__main__':
    unittest.main()

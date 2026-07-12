from __future__ import annotations

import unittest

from core.utils.config import GlobalConfig, normalize_max_parallel_conversions


class NormalizeParallelTests(unittest.TestCase):
    def test_default_and_clamp(self) -> None:
        self.assertEqual(normalize_max_parallel_conversions(None), 2)
        self.assertEqual(normalize_max_parallel_conversions(0), 2)
        self.assertEqual(normalize_max_parallel_conversions(-1), 2)
        self.assertEqual(normalize_max_parallel_conversions('3'), 3)
        self.assertEqual(normalize_max_parallel_conversions(8), 8)
        self.assertEqual(normalize_max_parallel_conversions(99), 8)

    def test_global_config_field(self) -> None:
        cfg = GlobalConfig({'max_parallel_conversions': 4})
        self.assertEqual(cfg.max_parallel_conversions, 4)
        self.assertEqual(cfg.to_local_dict()['max_parallel_conversions'], 4)
        cfg.apply_local_dict({'max_parallel_conversions': 1})
        self.assertEqual(cfg.max_parallel_conversions, 1)


if __name__ == '__main__':
    unittest.main()

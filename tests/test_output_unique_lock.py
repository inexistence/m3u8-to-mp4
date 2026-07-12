# tests/test_output_unique_lock.py
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from core.utils.output import resolve_unique_output_path


class OutputUniqueLockTests(unittest.TestCase):
    def test_parallel_calls_get_distinct_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            results: list[Path] = []
            barrier = threading.Barrier(8)
            lock = threading.Lock()

            def worker(i: int) -> None:
                barrier.wait()
                path = resolve_unique_output_path(
                    out_dir,
                    'output.mp4',
                    out_dir / f'video_{i}.m3u8',
                )
                # 立刻占位，模拟即将写入
                path.write_bytes(b'')
                with lock:
                    results.append(path)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(results), 8)
            self.assertEqual(len({p.resolve() for p in results}), 8)


if __name__ == '__main__':
    unittest.main()

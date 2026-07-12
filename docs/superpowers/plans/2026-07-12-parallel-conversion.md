# Parallel Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GUI 与 CLI 批量转换按固定并发数并行执行；支持「取消全部」与行内单任务取消；并行时输出路径不撞名。

**Architecture:** 新增 `core/batch_convert.py`（`ThreadPoolExecutor` + 每任务 `cancel_event`），`ConversionWorker` 与 `main.py` 共用。`GlobalConfig.max_parallel_conversions` 默认 `2`。输出路径解析加进程内锁。GUI 工具栏文案「取消全部」，任务行对 `PENDING`/`RUNNING` 提供行内取消。

**Tech Stack:** Python 3、`concurrent.futures.ThreadPoolExecutor`、`threading.Event`、`unittest` + `unittest.mock`（仓库未装 pytest）

**Spec:** `docs/superpowers/specs/2026-07-12-parallel-conversion-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| Modify: `config.yaml` | 默认 `max_parallel_conversions: 2` |
| Modify: `core/utils/config.py` | 加载/保存/规范化并发配置 |
| Modify: `core/utils/output.py` | `resolve_unique_output_path` 进程内锁 |
| Create: `core/batch_convert.py` | 批取消控制器 + 线程池批处理 |
| Modify: `gui/worker.py` | 调用批处理；`cancel()` / `cancel_task(i)` |
| Modify: `gui/settings_dialog.py` | 「同时转换数」设置 |
| Modify: `gui/task_list.py` | 行内取消按钮；工具栏「取消全部」 |
| Modify: `gui/app.py` | 接线 `cancel_task` |
| Modify: `main.py` | CLI 目录模式并行 |
| Create: `tests/test_config_parallel.py` | 配置规范化 |
| Create: `tests/test_output_unique_lock.py` | 并行撞名 |
| Create: `tests/test_batch_convert.py` | 并发上限、取消语义 |
| Modify: `tests/test_worker_cancel.py` | 适配每任务 Event |
| Create: `tests/test_worker_parallel.py` | Worker 并行与单任务取消 |
| Modify: `README.md` | 简述并行与设置项 |

测试命令统一：

```bash
python -m unittest <module> -v
```

Windows PowerShell 提交示例（本仓库在 Windows 上开发）：

```powershell
git add <files>
git commit -m "feat: short message"
```

---

### Task 1: 配置项 `max_parallel_conversions`

**Files:**
- Modify: `config.yaml`
- Modify: `core/utils/config.py`
- Create: `tests/test_config_parallel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_parallel.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_config_parallel -v`  
Expected: FAIL / ERROR — `normalize_max_parallel_conversions` 不存在或字段缺失

- [ ] **Step 3: Write minimal implementation**

在 `config.yaml` 末尾（`stream_selection` 附近）增加：

```yaml
# 同时转换的最大任务数（GUI / CLI 批量）
# 取值 1–8；默认 2
max_parallel_conversions: 2
```

在 `core/utils/config.py`：

```python
def normalize_max_parallel_conversions(value: object) -> int:
    """规范并发数：非法/缺失 → 2；小于 1 → 2；大于 8 → 8。"""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 2
    if n < 1:
        return 2
    if n > 8:
        return 8
    return n
```

`GlobalConfig.__init__` 增加：

```python
self.max_parallel_conversions: int = normalize_max_parallel_conversions(
    get_value(dict=config, key='max_parallel_conversions', default_value=2)
)
```

`to_local_dict` 增加 `'max_parallel_conversions': self.max_parallel_conversions`。

`apply_local_dict`：若键存在则 `self.max_parallel_conversions = normalize_max_parallel_conversions(data['max_parallel_conversions'])`。

`reload_from_disk`：同步 `self.max_parallel_conversions = fresh.max_parallel_conversions`。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_config_parallel -v`  
Expected: OK

- [ ] **Step 5: Commit**

```powershell
git add config.yaml core/utils/config.py tests/test_config_parallel.py
git commit -m "feat: add max_parallel_conversions config"
```

---

### Task 2: 设置对话框「同时转换数」

**Files:**
- Modify: `gui/settings_dialog.py`

- [ ] **Step 1: Add UI section**

在 `_build_ui` 的 `segment_group` 之后、`save_feedback` 之前增加分区，例如：

```python
parallel_group = self._add_section(
    body,
    '同时转换数',
    '批量转换时最多同时进行的任务数。数值越大通常越快，但也更占磁盘与 CPU。',
)
self.parallel_menu = ctk.CTkOptionMenu(
    parallel_group,
    values=[str(i) for i in range(1, 9)],
    height=32,
    font=t.font_body(),
)
self.parallel_menu.pack(fill='x', padx=t.SPACE_MD, pady=(t.SPACE_XS, t.SPACE_MD))
```

若窗口高度不够，将 `geometry('560x620')` 调整为约 `560x700`。

- [ ] **Step 2: Load / save**

`_load_values`：

```python
self.parallel_menu.set(str(self.global_config.max_parallel_conversions))
```

`_save`：在写其他字段后：

```python
self.global_config.max_parallel_conversions = normalize_max_parallel_conversions(
    self.parallel_menu.get()
)
```

顶部增加：`from core.utils.config import GlobalConfig, save_local_config, normalize_max_parallel_conversions`（替换原 import）。

- [ ] **Step 3: Manual smoke（可选）**

运行 `python gui_app.py`，打开设置，确认下拉为 1–8，保存后 `local_config.yaml` 含 `max_parallel_conversions`。

- [ ] **Step 4: Commit**

```powershell
git add gui/settings_dialog.py
git commit -m "feat: settings UI for parallel conversion count"
```

---

### Task 3: 输出路径进程内锁

**Files:**
- Modify: `core/utils/output.py`
- Create: `tests/test_output_unique_lock.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

约定：在锁内选定路径并 `touch()` 占位，避免并行撞名；FFmpeg 随后覆盖写入。取消清理须能删除 0 字节占位（核对 `ffmpeg_merge.py`）。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_output_unique_lock -v`  
Expected: FAIL 或偶发重复路径（当前无锁）。立即进入 Step 3。

- [ ] **Step 3: Implement locked unique path with touch**

```python
# core/utils/output.py
"""输出文件路径解析。"""
from pathlib import Path
import threading

_output_path_lock = threading.Lock()


def resolve_output_directory(output_directory: str | Path | None, source_directory: Path) -> Path:
    """解析输出目录；空值时使用源 m3u8 所在目录。"""
    if output_directory is None or not str(output_directory).strip():
        return source_directory.resolve()

    resolved_directory = Path(output_directory).expanduser().resolve()
    if not resolved_directory.exists():
        raise FileNotFoundError(f'输出目录不存在：{resolved_directory}')
    if not resolved_directory.is_dir():
        raise NotADirectoryError(f'输出路径不是目录：{resolved_directory}')
    return resolved_directory


def resolve_unique_output_path(output_dir: Path, base_name: str, source_m3u8: Path) -> Path:
    """在同目录下选择不冲突的 MP4 输出路径，并 touch 占位（进程内线程安全）。"""
    if not base_name.lower().endswith('.mp4'):
        base_name = f'{base_name}.mp4'

    output_dir = output_dir.resolve()
    name_stem = Path(base_name).stem
    source_stem = source_m3u8.resolve().stem

    with _output_path_lock:
        candidates = [output_dir / base_name]
        if source_stem != name_stem:
            candidates.append(output_dir / f'{name_stem}_{source_stem}.mp4')

        for path in candidates:
            if not path.exists():
                path.touch()
                return path

        prefix = f'{name_stem}_{source_stem}' if source_stem != name_stem else name_stem
        for i in range(2, 10000):
            path = output_dir / f'{prefix}_{i}.mp4'
            if not path.exists():
                path.touch()
                return path

    raise RuntimeError(f'无法为 {base_name} 找到可用输出文件名')
```

注意：取消时若转换未写出有效 MP4，可能留下 0 字节占位；现有取消清理半成品 MP4 应删除它。确认 `FfmpegMerger` 取消路径会删输出文件；若只删「已开始写入」的文件，需在取消清理中覆盖 0 字节文件。实现时核对 `ffmpeg_merge.py` 的删除逻辑，必要时对空占位也删除。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_output_unique_lock -v`  
Expected: OK

同时跑：`python -m unittest tests.test_ffmpeg_merge tests.test_ffmpeg_cancel -v`  
Expected: OK（回归）

- [ ] **Step 5: Commit**

```powershell
git add core/utils/output.py tests/test_output_unique_lock.py
git commit -m "fix: lock unique output path allocation for parallel converts"
```

---

### Task 4: `core/batch_convert.py` 批处理核心

**Files:**
- Create: `core/batch_convert.py`
- Create: `tests/test_batch_convert.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_batch_convert.py
from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.batch_convert import BatchCancelController, run_batch_conversions
from core.discovery import M3u8Entry
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus


def _task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class BatchConvertTests(unittest.TestCase):
    def test_respects_max_parallel(self) -> None:
        tasks = [_task(f'{i}.m3u8') for i in range(4)]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        current = 0
        peak = 0
        lock = threading.Lock()

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            nonlocal current, peak
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.05)
            with lock:
                current -= 1

        cancel = BatchCancelController.for_tasks(len(tasks))
        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            done = run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(done, 4)
        self.assertLessEqual(peak, 2)
        self.assertTrue(all(t.status == TaskStatus.DONE for t in tasks))

    def test_cancel_all_marks_running_error_and_pending_skipped(self) -> None:
        tasks = [_task('a.m3u8'), _task('b.m3u8'), _task('c.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        cancel = BatchCancelController.for_tasks(len(tasks))
        started = threading.Event()

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            started.set()
            while not cancel_event.is_set():
                time.sleep(0.01)
            raise ConversionCancelled()

        def trigger():
            started.wait(timeout=2)
            cancel.cancel_all()

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            threading.Thread(target=trigger, daemon=True).start()
            run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(tasks[0].status, TaskStatus.ERROR)
        self.assertEqual(tasks[0].error_message, '用户取消')
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        self.assertEqual(tasks[2].status, TaskStatus.SKIPPED)

    def test_cancel_pending_skips_without_convert(self) -> None:
        tasks = [_task('a.m3u8'), _task('b.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        cancel = BatchCancelController.for_tasks(len(tasks))
        cancel.cancel_task(1)
        calls = []

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            calls.append(cancel_event)

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            done = run_batch_conversions(tasks, config, cancel=cancel)

        self.assertEqual(done, 1)
        self.assertEqual(tasks[0].status, TaskStatus.DONE)
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
```

依赖约定（YAGNI）：`core/batch_convert.py` 可导入 `gui.models.ConversionTask` / `TaskStatus`。若日后要消除 core→gui，再抽 `core/task_models.py`（不在本计划范围）。

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_batch_convert -v`  
Expected: ERROR — `No module named 'core.batch_convert'`

- [ ] **Step 3: Implement batch convert**

```python
# core/batch_convert.py
"""批量并行转换。"""
from __future__ import annotations

import io
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Callable, Sequence

from core.m3u8converter import M3U8Converter
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig, normalize_max_parallel_conversions
from gui.models import ConversionTask, TaskStatus


ProgressCallback = Callable[[str, int, int | None], None]
EventCallback = Callable[[str], None]  # 粗粒度；Worker 用更细回调


@dataclass
class BatchCancelController:
    batch_cancel: threading.Event = field(default_factory=threading.Event)
    task_cancels: list[threading.Event] = field(default_factory=list)

    @classmethod
    def for_tasks(cls, count: int) -> BatchCancelController:
        return cls(task_cancels=[threading.Event() for _ in range(count)])

    def cancel_all(self) -> None:
        self.batch_cancel.set()
        for event in self.task_cancels:
            event.set()

    def cancel_task(self, index: int) -> None:
        if 0 <= index < len(self.task_cancels):
            self.task_cancels[index].set()


@dataclass
class BatchCallbacks:
    on_task_started: Callable[[int, ConversionTask], None] | None = None
    on_task_progress: Callable[[int, str, int, int | None], None] | None = None
    on_task_done: Callable[[int, ConversionTask], None] | None = None
    on_task_error: Callable[[int, ConversionTask, BaseException], None] | None = None
    on_log: Callable[[str], None] | None = None


def resolve_worker_count(config: GlobalConfig) -> int:
    return normalize_max_parallel_conversions(getattr(config, 'max_parallel_conversions', 2))


def run_batch_conversions(
    tasks: Sequence[ConversionTask],
    config: GlobalConfig,
    *,
    cancel: BatchCancelController,
    callbacks: BatchCallbacks | None = None,
) -> int:
    """并行转换；返回成功完成的任务数。"""
    callbacks = callbacks or BatchCallbacks()
    total = len(tasks)
    if total == 0:
        return 0
    if len(cancel.task_cancels) != total:
        raise ValueError('cancel.task_cancels length must match tasks')

    workers = resolve_worker_count(config)
    done_lock = threading.Lock()
    done_count = 0

    def convert_one(index: int, task: ConversionTask) -> None:
        nonlocal done_count
        if cancel.batch_cancel.is_set() or cancel.task_cancels[index].is_set():
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
            return

        task.status = TaskStatus.RUNNING
        if callbacks.on_task_started:
            callbacks.on_task_started(index, task)

        stream_index = task.selected_stream_index if task.is_master_playlist else None
        buffer = io.StringIO()
        cancel_event = cancel.task_cancels[index]

        def report_progress(phase: str, current: int, total_parts: int | None) -> None:
            if callbacks.on_task_progress:
                callbacks.on_task_progress(index, phase, current, total_parts)

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                converter = M3U8Converter(m3u8_index_file_path=task.path, config=config)
                converter.convert(
                    stream_index=stream_index,
                    progress_callback=report_progress,
                    cancel_event=cancel_event,
                )
            task.status = TaskStatus.DONE
            with done_lock:
                done_count += 1
            if callbacks.on_task_done:
                callbacks.on_task_done(index, task)
        except ConversionCancelled as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc) or '用户取消'
            if callbacks.on_task_error:
                callbacks.on_task_error(index, task, exc)
        except Exception as exc:
            task.status = TaskStatus.ERROR
            task.error_message = str(exc)
            buffer.write(traceback.format_exc())
            if callbacks.on_task_error:
                callbacks.on_task_error(index, task, exc)
        finally:
            output = buffer.getvalue().strip()
            if output and callbacks.on_log:
                callbacks.on_log(output)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(convert_one, index, task) for index, task in enumerate(tasks)]
        for future in as_completed(futures):
            future.result()

    for index, task in enumerate(tasks):
        if task.status == TaskStatus.PENDING and (
            cancel.batch_cancel.is_set() or cancel.task_cancels[index].is_set()
        ):
            task.status = TaskStatus.SKIPPED

    return done_count
```

`test_cancel_pending_skips_without_convert`：任务 1 预先 `cancel_task(1)`；`convert_one(1)` 开头应 SKIPPED 且不调 convert。

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_batch_convert -v`  
Expected: OK

- [ ] **Step 5: Commit**

```powershell
git add core/batch_convert.py tests/test_batch_convert.py
git commit -m "feat: add parallel batch conversion runner"
```

---

### Task 5: `ConversionWorker` 接入批处理

**Files:**
- Modify: `gui/worker.py`
- Modify: `tests/test_worker_cancel.py`
- Create: `tests/test_worker_parallel.py`

- [ ] **Step 1: Update cancel test for per-task events**

用下面完整内容替换 `tests/test_worker_cancel.py`：

```python
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.discovery import M3u8Entry
from core.utils.cancellation import ConversionCancelled
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus
from gui.worker import ConversionWorker, WorkerEvent


def _make_task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class WorkerCancelTests(unittest.TestCase):
    def test_cancelled_task_becomes_error_and_pending_skipped(self) -> None:
        task_a = _make_task('a.m3u8')
        task_b = _make_task('b.m3u8')
        events: list[WorkerEvent] = []
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        worker = ConversionWorker([task_a, task_b], config, events.append)

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            worker.cancel()
            raise ConversionCancelled()

        with patch('core.batch_convert.M3U8Converter') as converter_cls:
            converter_cls.return_value.convert.side_effect = fake_convert
            worker._run()

        self.assertEqual(task_a.status, TaskStatus.ERROR)
        self.assertEqual(task_a.error_message, '用户取消')
        self.assertEqual(task_b.status, TaskStatus.SKIPPED)

        kinds = [e.kind for e in events]
        self.assertIn('task_error', kinds)
        self.assertIn('finished', kinds)
        finished = next(e for e in events if e.kind == 'finished')
        self.assertEqual(finished.done_count, 0)
        self.assertNotIn('task_done', kinds)
        converter_cls.return_value.convert.assert_called_once()


if __name__ == '__main__':
    unittest.main()
```

并行单测：

```python
# tests/test_worker_parallel.py
from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.discovery import M3u8Entry
from core.utils.config import GlobalConfig
from gui.models import ConversionTask, TaskStatus
from gui.worker import ConversionWorker


def _make_task(name: str) -> ConversionTask:
    return ConversionTask(entry=M3u8Entry(path=Path(name)))


class WorkerParallelTests(unittest.TestCase):
    def test_cancel_task_skips_pending_only(self) -> None:
        tasks = [_make_task('a.m3u8'), _make_task('b.m3u8')]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 1
        worker = ConversionWorker(tasks, config, lambda e: None)
        worker.cancel_task(1)

        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = lambda **k: None
            worker._run()

        self.assertEqual(tasks[0].status, TaskStatus.DONE)
        self.assertEqual(tasks[1].status, TaskStatus.SKIPPED)
        cls.return_value.convert.assert_called_once()

    def test_parallel_peak_at_most_two(self) -> None:
        tasks = [_make_task(f'{i}.m3u8') for i in range(4)]
        config = MagicMock(spec=GlobalConfig)
        config.max_parallel_conversions = 2
        current = 0
        peak = 0
        lock = threading.Lock()

        def fake_convert(**kwargs):
            nonlocal current, peak
            with lock:
                current += 1
                peak = max(peak, current)
            time.sleep(0.05)
            with lock:
                current -= 1

        worker = ConversionWorker(tasks, config, lambda e: None)
        with patch('core.batch_convert.M3U8Converter') as cls:
            cls.return_value.convert.side_effect = fake_convert
            worker._run()

        self.assertLessEqual(peak, 2)
        self.assertTrue(all(t.status == TaskStatus.DONE for t in tasks))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify fail / outdated**

Run: `python -m unittest tests.test_worker_cancel tests.test_worker_parallel -v`  
Expected: FAIL（Worker 尚无 `cancel_task` / 未走 batch）

- [ ] **Step 3: Rewrite `gui/worker.py`**

保留 `WorkerEvent`、`map_task_progress`；`ConversionWorker` 改为：

```python
class ConversionWorker:
    def __init__(self, tasks, config, on_event):
        self.tasks = tuple(tasks)
        self.global_config = config
        self.on_event = on_event
        self._thread: threading.Thread | None = None
        self._cancel_controller = BatchCancelController.for_tasks(len(self.tasks))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._cancel_controller = BatchCancelController.for_tasks(len(self.tasks))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_controller.cancel_all()

    def cancel_task(self, task_index: int) -> None:
        self._cancel_controller.cancel_task(task_index)

    def _emit(self, kind, message='', task_index=-1, done_count=0, total_count=0,
              progress_percent=None, progress_phase='') -> None:
        self.on_event(WorkerEvent(...))

    def _run(self) -> None:
        total = len(self.tasks)
        if total == 0:
            self._emit('error', '请至少选择一个文件')
            self._emit('finished')
            return

        self._emit('started', total_count=total)
        done_box = {'n': 0}

        def on_started(index, task):
            self._emit('task_started', task.path.name, task_index=index,
                       done_count=done_box['n'], total_count=total)

        def on_progress(index, phase, current, total_parts):
            progress_phase, percent, label = map_task_progress(phase, current, total_parts)
            self._emit('task_progress', message=label, task_index=index,
                       progress_percent=percent, progress_phase=progress_phase)

        def on_done(index, task):
            done_box['n'] += 1
            self._emit('task_done', f'完成: {task.path.name}', task_index=index,
                       done_count=done_box['n'], total_count=total)

        def on_error(index, task, exc):
            self._emit('task_error', f'失败: {task.path.name} — {exc}', task_index=index,
                       done_count=done_box['n'], total_count=total)

        def on_log(text):
            self._emit('log', text)

        done = run_batch_conversions(
            self.tasks,
            self.global_config,
            cancel=self._cancel_controller,
            callbacks=BatchCallbacks(
                on_task_started=on_started,
                on_task_progress=on_progress,
                on_task_done=on_done,
                on_task_error=on_error,
                on_log=on_log,
            ),
        )
        self._emit('finished', done_count=done, total_count=total)
```

删除旧的 `_convert_one` 串行循环。`done_box` 与 `run_batch_conversions` 返回值应一致；优先使用返回的 `done`，`on_done` 内递增仅用于中间反馈。

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_worker_cancel tests.test_worker_parallel tests.test_batch_convert -v`  
Expected: OK

- [ ] **Step 5: Commit**

```powershell
git add gui/worker.py tests/test_worker_cancel.py tests/test_worker_parallel.py
git commit -m "feat: wire ConversionWorker to parallel batch runner"
```

---

### Task 6: GUI「取消全部」+ 行内取消

**Files:**
- Modify: `gui/task_list.py`
- Modify: `gui/app.py`

- [ ] **Step 1: Toolbar label**

将 `cancel_btn` 初始文案改为 `'取消全部'`。`app.py` 里 `cancel_btn.configure(..., text='正在取消…')` 与恢复时改为 `text='取消全部'`。

- [ ] **Step 2: TaskRow 行内取消**

`TaskRow.__init__` 增加可选 `on_cancel_task: Callable[[ConversionTask], None] | None = None`。

在 `status_badge` 旁增加小按钮（或放在进度行右侧）：

```python
self.cancel_task_btn = t.style_danger_button(
    ctk.CTkButton(self, text='取消', width=56, height=24, command=self._on_cancel_task),
)
self.cancel_task_btn.grid(row=0, column=3, rowspan=2, padx=(0, t.SPACE_MD), pady=t.SPACE_MD, sticky='e')
self.cancel_task_btn.grid_remove()
```

调整 `status_badge` 的 column 若需要。`_on_cancel_task` 调用 `self.on_cancel_task(self.task)`。

在 `refresh_status` / 新增 `update_cancel_visibility(batch_active: bool)`：当 `batch_active` 且 `task.status in {PENDING, RUNNING}` 时 `grid()`，否则 `grid_remove()`。

`set_enabled` 不要禁用行内取消按钮（转换中勾选禁用，但取消要可用）——在 `set_enabled(False)` 时仍 `cancel_task_btn.configure(state='normal')` 并按可见性显示。

- [ ] **Step 3: TaskList / App 接线**

`TaskList` 构造增加 `on_cancel_task`；`set_tasks` 创建 `TaskRow` 时传入。

`ConversionApp`：

```python
def _cancel_task(self, task: ConversionTask) -> None:
    if not self.is_converting or self.worker is None:
        return
    try:
        index = self._active_batch.index(task)
    except ValueError:
        return
    self.worker.cancel_task(index)
```

`refresh_rows` 后根据 `is_converting` 更新行内取消可见性。

在 `_handle_worker_event` 的 `task_started` / `task_done` / `task_error` / `finished` 时刷新行内取消按钮。

- [ ] **Step 4: Manual smoke**

启动 GUI，导入 ≥3 个任务，并发设为 2，开始转换：应看到多行「转换中」；行内取消一条 PENDING/RUNNING；「取消全部」停整批。

- [ ] **Step 5: Commit**

```powershell
git add gui/task_list.py gui/app.py
git commit -m "feat: per-task cancel and rename cancel-all button"
```

---

### Task 7: CLI 目录模式并行

**Files:**
- Modify: `main.py`
- Create: `tests/test_cli_batch.py`（可选，mock 批处理）

- [ ] **Step 1: Write failing CLI batch test**

```python
# tests/test_cli_batch.py
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

        with patch('main.ensure_ffmpeg'), \
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
```

注意：`main()` 内部 `get_global_config()`——需 patch 为返回同一 `config`，或断言 `run_batch` 被调用且任务数为 2。

更稳：

```python
with patch('main.get_global_config', return_value=config), \
     patch('main.ensure_ffmpeg'), \
     ...
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m unittest tests.test_cli_batch -v`  
Expected: FAIL

- [ ] **Step 3: Implement CLI**

```python
# main.py 关键部分
from core.batch_convert import BatchCancelController, BatchCallbacks, run_batch_conversions
from core.discovery import find_entry_m3u8, M3u8Entry
from gui.models import ConversionTask

def main(path_name: Path):
    try:
        ensure_ffmpeg()
    except RuntimeError:
        print(ffmpeg_missing_message(), file=sys.stderr)
        sys.exit(1)

    config = get_global_config()

    if os.path.isfile(path_name):
        handle_file(index_file_path=path_name, config=config)
    elif os.path.isdir(path_name):
        index_files = find_entry_m3u8(path_name)
        if not index_files:
            print('no .m3u8 files found in', path_name)
            return
        print(f'found {len(index_files)} .m3u8 file(s)')
        tasks = [ConversionTask(entry=M3u8Entry(path=p)) for p in index_files]
        cancel = BatchCancelController.for_tasks(len(tasks))

        def on_started(index, task):
            print(f'[{index + 1}/{len(tasks)}] start', task.path)

        def on_done(index, task):
            print(f'[{index + 1}/{len(tasks)}] done', task.path)

        def on_error(index, task, exc):
            print(f'[{index + 1}/{len(tasks)}] fail', task.path, exc)

        done = run_batch_conversions(
            tasks,
            config,
            cancel=cancel,
            callbacks=BatchCallbacks(
                on_task_started=on_started,
                on_task_done=on_done,
                on_task_error=on_error,
            ),
        )
        print(f'finished {done}/{len(tasks)}')
    else:
        raise TypeError('not file nor dir')
```

删除 `# TODO multi thread`。单文件路径仍走 `handle_file`。

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_cli_batch -v`  
Expected: OK

- [ ] **Step 5: Commit**

```powershell
git add main.py tests/test_cli_batch.py
git commit -m "feat: parallel CLI directory batch conversion"
```

---

### Task 8: README + 全量回归

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Docs**

在功能特性或 GUI 使用中补充：

- 批量转换默认同时进行 2 个任务，可在设置中改为 1–8
- 转换中可「取消全部」或取消单个排队/进行中任务
- CLI 扫描目录时使用同一并发配置

- [ ] **Step 2: Full regression**

```bash
python -m unittest tests.test_config_parallel tests.test_output_unique_lock tests.test_batch_convert tests.test_worker_cancel tests.test_worker_parallel tests.test_cli_batch tests.test_cancellation tests.test_ffmpeg_merge tests.test_ffmpeg_cancel tests.test_parser_cancel tests.test_converter_cancel_wiring tests.test_choose_output_directory -v
```

Expected: 全部 OK

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "docs: document parallel conversion settings"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| `max_parallel_conversions` 默认 2，可配置 1–8 | 1, 2 |
| GUI + CLI 并行 | 5, 7 |
| ThreadPoolExecutor 共享批处理 | 4 |
| 全局取消全部 RUNNING + PENDING SKIPPED | 4, 5 |
| 行内取消 RUNNING→ERROR / PENDING→SKIPPED | 4, 5, 6 |
| 工具栏「取消全部」文案 | 6 |
| 输出路径不撞名 | 3 |
| 多行同时 RUNNING 进度 | 5（事件模型已有 task_index） |
| `max_parallel=1` 等价串行 | 4, 5 测试 |
| 不按 CPU 自动算 | 1（仅固定值） |

## 实现时注意

1. **core → gui 依赖**：`core/batch_convert.py` 导入 `gui.models`。若执行中要消除，再抽 `core/task_models.py`（非本计划必做）。
2. **touch 占位**：确认取消清理会删除 0 字节输出；否则在 `ConversionCancelled` 路径补删。
3. **`done_count` 线程安全**：中间 UI 反馈用锁或仅用最终返回值。
4. **PowerShell**：勿使用 bash heredoc；用 `git commit -m "..."`。

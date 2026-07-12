# Cancel Conversion Mid-Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户点取消后，当前任务在合片分片边界与 FFmpeg 封装阶段可尽快停止；被中断任务标为 `ERROR`（文案「用户取消」），后续未开跑任务标 `SKIPPED`，并清理临时文件与半成品 MP4。

**Architecture:** 将 `ConversionWorker._cancel`（`threading.Event`）经 `M3U8Converter.convert` 传给 `SimpleM3U8TsParser` 与 `FfmpegMerger`。各层通过 `_raise_if_cancelled()` 抛出 `ConversionCancelled`。`FfmpegMerger.finish()` 在已取消时只清理不封装；`_run_ffmpeg` 在 progress 循环中 `terminate`/`kill` 子进程。Worker 捕获取消后将当前任务标 `ERROR` 并发 `task_error`。

**Tech Stack:** Python 3、`threading.Event`、`subprocess.Popen`、`unittest` + `unittest.mock`（仓库未装 pytest）

**Spec:** `docs/superpowers/specs/2026-07-12-cancel-conversion-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| Create: `core/utils/cancellation.py` | `ConversionCancelled` 异常 |
| Modify: `core/merge/ffmpeg_merge.py` | `cancel_event`、取消时清理/杀进程、删半成品 MP4 |
| Modify: `core/m3u8_ts_parser.py` | 分片处理前检查取消 |
| Modify: `core/m3u8converter.py` | 向下传递 `cancel_event` |
| Modify: `gui/worker.py` | 传入 event；取消 → 当前任务 ERROR |
| Create: `tests/test_cancellation.py` | 取消异常与 raise helper（若 helper 抽出） |
| Create: `tests/test_ffmpeg_cancel.py` | FFmpeg / finish 取消行为 |
| Create: `tests/test_parser_cancel.py` | 分片边界取消 |
| Create: `tests/test_worker_cancel.py` | Worker 状态映射 |

GUI（`gui/app.py`）无需改：已有 `worker.cancel()` 与 ERROR 详情面板。

测试命令统一用：

```bash
python -m unittest <module> -v
```

---

### Task 1: `ConversionCancelled` 异常

**Files:**
- Create: `core/utils/cancellation.py`
- Create: `tests/test_cancellation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cancellation.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cancellation -v`  
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'core.utils.cancellation'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/utils/cancellation.py
"""转换取消。"""


class ConversionCancelled(Exception):
    """用户请求取消转换。"""

    def __init__(self, message: str = '用户取消') -> None:
        super().__init__(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cancellation -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/utils/cancellation.py tests/test_cancellation.py
git commit -m "$(cat <<'EOF'
feat: add ConversionCancelled exception

EOF
)"
```

---

### Task 2: `FfmpegMerger` 取消时跳过封装并清理

**Files:**
- Modify: `core/merge/ffmpeg_merge.py`
- Create: `tests/test_ffmpeg_cancel.py`
- Test also touches existing: `tests/test_ffmpeg_merge.py`（应仍通过）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ffmpeg_cancel.py
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


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ffmpeg_cancel -v`  
Expected: FAIL — `TypeError: ... unexpected keyword argument 'cancel_event'` 或未抛 `ConversionCancelled`

- [ ] **Step 3: Write minimal implementation**

在 `FfmpegMerger.__init__` 增加：

```python
cancel_event: threading.Event | None = None,
# ...
self._cancel_event = cancel_event
self._process = None
```

需要 `import threading`（若只用 `Event | None` 可用 `from __future__ import annotations` + `threading.Event`，并 `import threading`）。

增加：

```python
def _raise_if_cancelled(self) -> None:
    if self._cancel_event is not None and self._cancel_event.is_set():
        raise ConversionCancelled()

def _cleanup_temp(self) -> None:
    if self.merged_ts_file is not None:
        self.merged_ts_file.close()
        self.merged_ts_file = None
    if self.tmp_dir is not None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.tmp_dir = None

def _remove_incomplete_output(self) -> None:
    try:
        self.target_file_path.unlink(missing_ok=True)
    except OSError:
        pass
```

改写 `finish()` 逻辑要点：

1. 关闭 pbar（保持现有）
2. 若 `merged_ts_file is not None`：先 close 文件句柄（设为 None），然后：
   - 若已取消：`_cleanup_temp()`、`_remove_incomplete_output()`、`raise ConversionCancelled()`
   - 否则走现有 FFmpeg 封装；`finally` 里 `_cleanup_temp()`
3. 仅有 tmp_dir 时同样 `_cleanup_temp()`

`from core.utils.cancellation import ConversionCancelled`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_ffmpeg_cancel tests.test_ffmpeg_merge -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/merge/ffmpeg_merge.py tests/test_ffmpeg_cancel.py
git commit -m "$(cat <<'EOF'
feat: skip ffmpeg packaging when conversion is cancelled

EOF
)"
```

---

### Task 3: `FfmpegMerger._run_ffmpeg` 可终止子进程

**Files:**
- Modify: `core/merge/ffmpeg_merge.py`
- Modify: `tests/test_ffmpeg_cancel.py`

- [ ] **Step 1: Write the failing test**

追加到 `tests/test_ffmpeg_cancel.py`：

```python
class FfmpegMergerCancelProcessTests(unittest.TestCase):
    def test_run_ffmpeg_terminates_process_when_cancelled(self) -> None:
        cancel = threading.Event()
        mock_proc = MagicMock()
        # 第一行触发进度检查前先 set cancel
        mock_proc.stdout = iter(['out_time_ms=1000\n'])
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = 1

        def on_progress(phase, current, total):
            cancel.set()

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp4'
            merger = FfmpegMerger(target, progress_callback=on_progress, cancel_event=cancel)
            with patch('core.merge.ffmpeg_merge.subprocess.Popen', return_value=mock_proc):
                with self.assertRaises(ConversionCancelled):
                    merger._run_ffmpeg(['ffmpeg', '-y', '-i', 'in.ts', 'out.mp4'])
            mock_proc.terminate.assert_called()
            mock_proc.wait.assert_called()
```

更稳妥的写法（不依赖 progress 回调时机）：在读到第一行后检查 cancel——测试里先 `cancel.set()`，再调用 `_run_ffmpeg`，循环内一读行就应终止：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.FAKESECRET_q1r2s3t4u5v6w7x8y9z0 -v`  
Expected: FAIL — 未调用 `terminate` 或未抛取消 / 未删文件

- [ ] **Step 3: Write minimal implementation**

改写 `_run_ffmpeg`：

```python
def _run_ffmpeg(self, command: list[str]) -> None:
    self._report_packaging_progress()
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    self._process = process
    try:
        assert process.stdout is not None
        for line in process.stdout:
            self._raise_if_cancelled()
            out_time_us = parse_ffmpeg_progress_line(line)
            if out_time_us is not None:
                self._report_packaging_progress(out_time_us)
        self._raise_if_cancelled()
        returncode = process.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        if self._media_duration_ms is not None:
            self._report_packaging_progress(self._media_duration_ms * 1000)
    except ConversionCancelled:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self._remove_incomplete_output()
        raise
    finally:
        self._process = None
```

注意：循环开始前若已 cancel，应在进入循环后立刻 `_raise_if_cancelled()`（上面已有）。若 stdout 为空且已 cancel，循环后的 `_raise_if_cancelled()` 也会触发。

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_ffmpeg_cancel tests.test_ffmpeg_merge -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/merge/ffmpeg_merge.py tests/test_ffmpeg_cancel.py
git commit -m "$(cat <<'EOF'
feat: terminate ffmpeg process on cancel

EOF
)"
```

---

### Task 4: Parser 分片边界检查取消

**Files:**
- Modify: `core/m3u8_ts_parser.py`
- Create: `tests/test_parser_cancel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parser_cancel.py
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from core.m3u8_ts_parser import SimpleM3U8TsParser
from core.utils.cancellation import ConversionCancelled


class ParserCancelTests(unittest.TestCase):
    def test_decrypt_and_merge_raises_when_cancelled(self) -> None:
        cancel = threading.Event()
        cancel.set()
        merger = MagicMock()
        parser = SimpleM3U8TsParser(__file__, merger, cancel_event=cancel)
        with self.assertRaises(ConversionCancelled):
            parser._SimpleM3U8TsParser__decrypt_and_merge_ts('seg001.ts')
        merger.append.assert_not_called()


if __name__ == '__main__':
    unittest.main()
```

（若不愿测 name-mangled 私有方法，可改为公开 `_raise_if_cancelled` + 在 `__decrypt_and_merge_ts` 开头调用，测试改为调用 `parser._raise_if_cancelled()` 并用集成方式 mock `file.read_lines`；优先测真实入口：）

更清晰的替代测试——只验证公开辅助方法 + merge 路径中会调用：

```python
def test_raise_if_cancelled(self) -> None:
    cancel = threading.Event()
    cancel.set()
    parser = SimpleM3U8TsParser(__file__, MagicMock(), cancel_event=cancel)
    with self.assertRaises(ConversionCancelled):
        parser._raise_if_cancelled()
```

并另加：

```python
def test_handle_ts_line_checks_cancel_before_read(self) -> None:
    cancel = threading.Event()
    cancel.set()
    merger = MagicMock()
    parser = SimpleM3U8TsParser(__file__, merger, cancel_event=cancel)
    with self.assertRaises(ConversionCancelled):
        parser._SimpleM3U8TsParser__handle_line(0, 'seg001.ts')
    merger.append.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_parser_cancel -v`  
Expected: FAIL — 无 `cancel_event` / `_raise_if_cancelled`

- [ ] **Step 3: Write minimal implementation**

`SimpleM3U8TsParser.__init__` 增加 `cancel_event: threading.Event | None = None`，保存为 `self._cancel_event`。

```python
def _raise_if_cancelled(self) -> None:
    if self._cancel_event is not None and self._cancel_event.is_set():
        raise ConversionCancelled()
```

在 `__decrypt_and_merge_ts` 中，在确认 `line.endswith('.ts')` 之后、`open(ts_file)` 之前调用 `self._raise_if_cancelled()`。

`merge()` 的 `finally: self.ts_merger.finish()` 保持不变——取消后 `FfmpegMerger.finish()` 会清理并再抛 `ConversionCancelled`。若循环已抛出，Python 3 中 `finally` 再抛会替换原异常，最终仍为 `ConversionCancelled`，可接受。

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_parser_cancel -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/m3u8_ts_parser.py tests/test_parser_cancel.py
git commit -m "$(cat <<'EOF'
feat: check cancel event before each ts segment

EOF
)"
```

---

### Task 5: Converter 传递 `cancel_event`

**Files:**
- Modify: `core/m3u8converter.py`
- Create: `tests/test_converter_cancel_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_converter_cancel_wiring.py
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
        config.stream_selection = 0
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
```

（按实际 `FfmpegMerger` / `SimpleM3U8TsParser` 调用是位置参数还是关键字参数调整断言：`call_args` 检查 kwargs 或 args。）

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_converter_cancel_wiring -v`  
Expected: FAIL — `convert()` 无 `cancel_event` 或未传入下游

- [ ] **Step 3: Write minimal implementation**

```python
def convert(
    self,
    stream_index: int | None = None,
    progress_callback: Callable[[str, int, int | None], None] | None = None,
    cancel_event: threading.Event | None = None,
):
    # ... existing setup ...
    merger = FfmpegMerger(output_path, progress_callback=progress_callback, cancel_event=cancel_event)
    ts_parser = SimpleM3U8TsParser(
        ts_infos_index_file_path,
        merger,
        aes_iv_mode=self.config.aes_iv_mode,
        cancel_event=cancel_event,
    )
    # ... rest unchanged ...
```

`import threading`（配合 `from __future__ import annotations` 亦可）。

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_converter_cancel_wiring -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/m3u8converter.py tests/test_converter_cancel_wiring.py
git commit -m "$(cat <<'EOF'
feat: pass cancel_event through M3U8Converter

EOF
)"
```

---

### Task 6: Worker 取消 → 当前任务 ERROR

**Files:**
- Modify: `gui/worker.py`
- Create: `tests/test_worker_cancel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker_cancel.py
from __future__ import annotations

import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.utils.cancellation import ConversionCancelled
from gui.models import ConversionTask, TaskStatus
from gui.worker import ConversionWorker


def _make_task(name: str = 'a.m3u8') -> ConversionTask:
    entry = MagicMock()
    entry.path = Path(name)
    entry.is_master_playlist = False
    entry.stream_labels = []
    task = ConversionTask(entry=entry)
    task.selected = True
    return task


class WorkerCancelTests(unittest.TestCase):
    def test_cancelled_running_task_marked_error(self) -> None:
        task_a = _make_task('a.m3u8')
        task_b = _make_task('b.m3u8')
        events: list = []

        def on_event(event):
            events.append(event)

        worker = ConversionWorker((task_a, task_b), MagicMock(), on_event)

        def fake_convert(*, stream_index=None, progress_callback=None, cancel_event=None):
            cancel_event.set()
            raise ConversionCancelled()

        with patch('gui.worker.M3U8Converter') as conv_cls:
            conv_cls.return_value.convert.side_effect = (
                lambda *a, **k: fake_convert(**k)
            )
            worker._cancel = threading.Event()
            worker._run()

        self.assertEqual(task_a.status, TaskStatus.ERROR)
        self.assertEqual(task_a.error_message, '用户取消')
        self.assertEqual(task_b.status, TaskStatus.SKIPPED)
        kinds = [e.kind for e in events]
        self.assertIn('task_error', kinds)
        self.assertIn('finished', kinds)


if __name__ == '__main__':
    unittest.main()
```

（`ConversionTask` 真实构造若需要 `M3u8Entry`，按 `gui/models.py` 调整 fixture。）

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_worker_cancel -v`  
Expected: FAIL — 当前任务被标成 ERROR 以外的状态，或未传 `cancel_event`

- [ ] **Step 3: Write minimal implementation**

在 `_convert_one`：

```python
from core.utils.cancellation import ConversionCancelled

# convert 调用：
converter.convert(
    stream_index=stream_index,
    progress_callback=report_progress,
    cancel_event=self._cancel,
)
```

异常处理：

```python
except ConversionCancelled as exc:
    task.status = TaskStatus.ERROR
    task.error_message = str(exc) or '用户取消'
    raise
except Exception as exc:
    task.status = TaskStatus.ERROR
    task.error_message = str(exc)
    buffer.write(traceback.format_exc())
    raise
```

`_run` 中对 `ConversionCancelled` 与普通异常都已 `task_error` 即可（当前 `except Exception` 已覆盖，因为 `ConversionCancelled` 是 `Exception` 子类）。确认 `done` 不因取消递增（现有 `except` 分支已不 `done += 1`）。

取消后循环继续：后续 `PENDING` → `SKIPPED`（现有 `if self._cancel.is_set()` 逻辑）。注意：`task_a` 已被标 `ERROR`，不要在后续逻辑里改成 `SKIPPED`。

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_worker_cancel -v`  
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add gui/worker.py tests/test_worker_cancel.py
git commit -m "$(cat <<'EOF'
feat: mark interrupted task as ERROR on cancel

EOF
)"
```

---

### Task 7: 全量回归

- [ ] **Step 1: Run all new/related tests**

```bash
python -m unittest tests.test_cancellation tests.test_ffmpeg_merge tests.test_ffmpeg_cancel tests.test_parser_cancel tests.test_converter_cancel_wiring tests.test_worker_cancel tests.test_choose_output_directory -v
```

Expected: 全部 OK

- [ ] **Step 2: Manual smoke（可选但推荐）**

1. 启动 GUI，加入至少 2 个任务  
2. 开始转换，在合片进度中点取消 → 当前任务失败详情为「用户取消」，后续为已跳过  
3. 再跑一次，在 FFmpeg 封装进度中点取消 → 子进程结束，半成品 MP4 不残留，详情同上  

- [ ] **Step 3: Final commit if any leftover**

仅当有未提交修正时再提交。

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| `ConversionCancelled` | Task 1 |
| `cancel_event` 下传 | Task 5 |
| 分片边界检查 | Task 4 |
| `finish()` 取消只清理不封装 | Task 2 |
| FFmpeg terminate/kill + 删半成品 | Task 3 |
| Worker：当前 ERROR「用户取消」，后续 SKIPPED | Task 6 |
| CLI 不传 event 行为不变 | Task 5 默认 `None` |
| GUI 详情复用 ERROR 面板 | 无需改代码（Task 6 发 `task_error`） |
| 测试覆盖 | Tasks 1–6 + 7 |

## Placeholder / Consistency Review

- 异常默认文案统一为「用户取消」
- 参数名统一 `cancel_event: threading.Event | None`
- 测试运行器统一 `python -m unittest`（非 pytest）

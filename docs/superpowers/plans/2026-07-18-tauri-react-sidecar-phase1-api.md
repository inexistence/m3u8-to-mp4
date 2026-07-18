# Tauri React Sidecar — Phase 1: 模型上移 + Python Sidecar API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ConversionTask`/`TaskStatus` 从 `gui` 上移到 `core`，并实现可独立测试的 FastAPI sidecar（REST + WebSocket），复用现有 `batch_convert`。

**Architecture:** Sidecar 监听 `127.0.0.1` 动态端口；React 持有队列展示态；转换期间 sidecar 用 `task_id` 映射批次任务，经线程安全队列把 `WorkerEvent` 等价事件推到 WebSocket。本阶段不建 Tauri/React。

**Tech Stack:** Python 3.10+、FastAPI、Uvicorn、`httpx`/`starlette.testclient`、`unittest`、现有 `core/` 与 `gui.worker.map_task_progress`

**Spec:** `docs/superpowers/specs/2026-07-18-tauri-react-sidecar-design.md`

**Plan series:**
1. 本文件 — Sidecar API（本阶段交付后可用 curl/测试客户端验证）
2. `2026-07-18-tauri-react-sidecar-phase2-ui.md` — React 队列 UI
3. `2026-07-18-tauri-react-sidecar-phase3-shell.md` — Tauri 壳、打包、移除旧 GUI

## Global Constraints

- Sidecar 仅绑定 `127.0.0.1`
- 端口由环境变量 `M3U8_SIDECAR_PORT` 指定；未设置时使用 `0`（由 OS 分配）并在启动日志打印实际端口
- 任务跨进程身份使用字符串 `task_id`（UUID），禁止用列表下标作为 API 身份
- 批次行为与现 GUI 一致：convert 冻结本批；运行中可继续 scan（本阶段 API 不阻止 scan）
- 测试命令：`python -m unittest <module> -v`
- Windows PowerShell 提交：`git add <files>; git commit -m "message"`
- 不修改 CLI 用户可见行为（仅允许 import 路径从 `gui.models` 改为 `core.models`）

---

## File Structure

| File | Responsibility |
|------|----------------|
| Create: `core/models.py` | `TaskStatus`、`ConversionTask`（从 `gui/models.py` 迁入） |
| Modify: `gui/models.py` | 再导出，保持短期兼容 |
| Modify: `core/batch_convert.py` | 改为 `from core.models import ...` |
| Modify: `main.py`、`gui/*`、`tests/test_*` | 改 import（或经 `gui.models` 再导出） |
| Create: `sidecar/__init__.py` | 包标记 |
| Create: `sidecar/schemas.py` | Pydantic 请求/响应/事件模型 |
| Create: `sidecar/events.py` | 线程安全事件总线 |
| Create: `sidecar/session.py` | 配置、批次、cancel、快照 |
| Create: `sidecar/app.py` | FastAPI 路由 |
| Create: `sidecar/__main__.py` | `python -m sidecar` 入口 |
| Create: `tests/test_core_models_export.py` | 模型位置 |
| Create: `tests/test_sidecar_api.py` | REST + 批次快照 |
| Create: `tests/test_sidecar_ws.py` | WebSocket 事件 |
| Modify: `requirements.txt` | 增加 `fastapi`、`uvicorn[standard]` |

---

### Task 1: 将 `ConversionTask` / `TaskStatus` 上移到 `core`

**Files:**
- Create: `core/models.py`
- Modify: `gui/models.py`
- Modify: `core/batch_convert.py`
- Modify: `main.py`
- Test: `tests/test_core_models_export.py`

**Interfaces:**
- Produces: `core.models.TaskStatus`、`core.models.ConversionTask`（字段与现 `gui.models` 完全一致）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core_models_export.py
from __future__ import annotations

import unittest
from pathlib import Path

from core.discovery import M3u8Entry
from core.models import ConversionTask, TaskStatus


class CoreModelsExportTests(unittest.TestCase):
    def test_task_defaults(self) -> None:
        task = ConversionTask(entry=M3u8Entry(path=Path('a.m3u8')))
        self.assertTrue(task.selected)
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.error_message, '')
        self.assertEqual(task.path, Path('a.m3u8').resolve() if Path('a.m3u8').exists() else task.entry.path)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_core_models_export -v`  
Expected: FAIL/ERROR — `No module named 'core.models'`

- [ ] **Step 3: Write minimal implementation**

将 `gui/models.py` 的全部内容复制到 `core/models.py`（包文档字符串改为 `"""共享转换任务模型。"""`）。

将 `gui/models.py` 改为再导出：

```python
"""GUI 数据模型（兼容再导出；新代码请使用 core.models）。"""
from core.models import ConversionTask, TaskStatus

__all__ = ['ConversionTask', 'TaskStatus']
```

将 `core/batch_convert.py` 与 `main.py` 的 import 改为：

```python
from core.models import ConversionTask, TaskStatus  # batch_convert 需要两者；main 仅 ConversionTask
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m unittest tests.test_core_models_export tests.test_batch_convert tests.test_worker_parallel tests.test_worker_cancel -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add core/models.py gui/models.py core/batch_convert.py main.py tests/test_core_models_export.py
git commit -m "refactor: move ConversionTask models into core"
```

---

### Task 2: Sidecar 依赖与事件总线

**Files:**
- Modify: `requirements.txt`
- Create: `sidecar/__init__.py`
- Create: `sidecar/events.py`
- Test: `tests/test_sidecar_events.py`

**Interfaces:**
- Produces:
  - `class EventBus:`
    - `def publish(self, event: dict) -> None`
    - `def subscribe(self) -> queue.SimpleQueue`
    - `def unsubscribe(self, q: queue.SimpleQueue) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sidecar_events.py
from __future__ import annotations

import unittest

from sidecar.events import EventBus


class EventBusTests(unittest.TestCase):
    def test_publish_reaches_subscriber(self) -> None:
        bus = EventBus()
        q = bus.subscribe()
        bus.publish({'type': 'task_progress', 'task_id': 'a'})
        self.assertEqual(q.get_nowait(), {'type': 'task_progress', 'task_id': 'a'})
        bus.unsubscribe(q)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sidecar_events -v`  
Expected: FAIL/ERROR — `sidecar.events` 不存在

- [ ] **Step 3: Implement + deps**

`requirements.txt` 追加：

```text
fastapi==0.116.1
uvicorn[standard]==0.35.0
httpx==0.28.1
```

```python
# sidecar/__init__.py
"""本地 FastAPI sidecar：为桌面 UI 暴露转换 API。"""

# sidecar/events.py
from __future__ import annotations

import queue
import threading


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.SimpleQueue] = []

    def subscribe(self) -> queue.SimpleQueue:
        q: queue.SimpleQueue = queue.SimpleQueue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.SimpleQueue) -> None:
        with self._lock:
            self._subscribers = [item for item in self._subscribers if item is not q]

    def publish(self, event: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)
```

- [ ] **Step 4: Install deps and run test**

```powershell
pip install -r requirements.txt
python -m unittest tests.test_sidecar_events -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt sidecar/__init__.py sidecar/events.py tests/test_sidecar_events.py
git commit -m "feat: add sidecar event bus and FastAPI deps"
```

---

### Task 3: Session — scan / config / batch 快照

**Files:**
- Create: `sidecar/schemas.py`
- Create: `sidecar/session.py`
- Test: `tests/test_sidecar_session.py`

**Interfaces:**
- Consumes: `core.discovery.find_entry_m3u8_from_paths`、`M3u8Entry`、`core.models`、`core.utils.config`、`gui.worker.map_task_progress`、`core.batch_convert`
- Produces: `SidecarSession` with:
  - `scan(paths: list[str], known_paths: list[str]) -> ScanResult`
  - `get_config() -> dict` / `put_config(data: dict) -> dict`
  - `ffmpeg_status() -> dict`
  - `start_convert(tasks: list[ConvertTaskIn]) -> None`（已在跑则抛错）
  - `cancel_all() -> None` / `cancel_task(task_id: str) -> None`
  - `batch_snapshot() -> dict`
  - `bus: EventBus`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sidecar_session.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidecar.session import SidecarSession


class SidecarSessionTests(unittest.TestCase):
    def test_scan_dedupes_against_known_paths(self) -> None:
        session = SidecarSession()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'index.m3u8'
            target.write_text('#EXTM3U\n#EXTINF:1,\nseg.ts\n', encoding='utf-8')
            (root / 'seg.ts').write_bytes(b'\x00')
            first = session.scan([str(root)], known_paths=[])
            self.assertEqual(first.added, 1)
            second = session.scan([str(root)], known_paths=[str(target.resolve())])
            self.assertEqual(second.added, 0)
            self.assertEqual(second.duplicates, 1)

    def test_batch_snapshot_idle(self) -> None:
        session = SidecarSession()
        snap = session.batch_snapshot()
        self.assertFalse(snap['is_converting'])
        self.assertEqual(snap['tasks'], [])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sidecar_session -v`  
Expected: FAIL/ERROR — `SidecarSession` 不存在

- [ ] **Step 3: Implement schemas + session**

```python
# sidecar/schemas.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    paths: list[str]
    known_paths: list[str] = Field(default_factory=list)


class EntryOut(BaseModel):
    path: str
    is_master_playlist: bool
    stream_labels: list[str]
    selected_stream_index: int


class ScanResult(BaseModel):
    entries: list[EntryOut]
    added: int
    duplicates: int
    unparseable: int
    message: str


class ConvertTaskIn(BaseModel):
    task_id: str
    path: str
    selected_stream_index: int = 0


class ConvertRequest(BaseModel):
    tasks: list[ConvertTaskIn]


class ConfigUpdate(BaseModel):
    skip_first_part: bool | None = None
    output_file_name: str | None = None
    output_directory: str | None = None
    reset_decryption_if_part_changed: bool | None = None
    aes_iv_mode: str | None = None
    max_parallel_conversions: int | None = None
```

`sidecar/session.py` 要点（实现时写全文件）：

1. 持有 `EventBus`、`GlobalConfig`（`get_global_config()`）、`_is_converting`、`_cancel: BatchCancelController | None`、`_batch: list[tuple[str, ConversionTask]]`、`_thread`
2. `scan`：`find_entry_m3u8_from_paths` → 对每个 path `M3u8Entry.from_path`；`known` 用 `Path.resolve()` 集合计 duplicates；失败计 unparseable；`message` 复用 `gui.task_list.scan_feedback` 文案函数（可 import）
3. `start_convert`：若已在转换 raise `RuntimeError('conversion already running')`；构建 `ConversionTask` 列表（按请求顺序）；`BatchCancelController.for_tasks(n)`；后台线程调用 `run_batch_conversions`；callbacks 里用 `map_task_progress`，`publish` 事件字典：

```python
{
  'type': 'task_progress',  # 或 task_started / task_done / task_error / task_skipped / batch_progress / batch_finished
  'task_id': task_id,
  'message': '...',
  'done_count': 0,
  'total_count': n,
  'progress_percent': 50,
  'progress_phase': 'merging',
  'status': 'running',  # 对终态事件填 pending/running/done/error/skipped
  'error_message': '',
}
```

4. 批次结束后 `publish({'type': 'batch_finished', ...})`，清除 `_is_converting`
5. `cancel_task`：按 `task_id` 找 index 调 `cancel.cancel_task(index)`
6. `batch_snapshot`：返回 `{is_converting, tasks: [{task_id, status, error_message, progress_percent, progress_phase, message}]}`

将 `gui.task_list.scan_feedback` 的 import 若造成 UI 依赖过重，可把 `scan_feedback` / `conversion_feedback` / `batch_feedback` 三个纯函数抽到 `core/queue_messages.py`（本 Task 内完成，并改 `gui.task_list` 再导出或改 import）。**优先抽取**，避免 sidecar 依赖 CustomTkinter 模块副作用。

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_sidecar_session -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add sidecar/schemas.py sidecar/session.py core/queue_messages.py gui/task_list.py tests/test_sidecar_session.py
git commit -m "feat: add sidecar session for scan and batch state"
```

---

### Task 4: FastAPI 路由与 health/config/ffmpeg

**Files:**
- Create: `sidecar/app.py`
- Create: `sidecar/__main__.py`
- Test: `tests/test_sidecar_api.py`

**Interfaces:**
- Produces: `create_app(session: SidecarSession | None = None) -> FastAPI`
- Routes per spec: `/api/health`、`/api/scan`、`/api/config`、`/api/convert`、`/api/cancel`、`/api/cancel/{task_id}`、`/api/ffmpeg-status`、`/api/batch`、`/ws`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sidecar_api.py
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.session import SidecarSession


class SidecarApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = SidecarSession()
        self.client = TestClient(create_app(self.session))

    def test_health(self) -> None:
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'ok': True})

    def test_config_roundtrip(self) -> None:
        res = self.client.get('/api/config')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('max_parallel_conversions', body)
        body['max_parallel_conversions'] = 3
        put = self.client.put('/api/config', json=body)
        self.assertEqual(put.status_code, 200)
        self.assertEqual(put.json()['max_parallel_conversions'], 3)

    def test_batch_idle(self) -> None:
        res = self.client.get('/api/batch')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()['is_converting'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sidecar_api -v`  
Expected: FAIL/ERROR — `create_app` 不存在

- [ ] **Step 3: Implement `create_app` + `__main__`**

`sidecar/app.py`：

- `GET /api/health` → `{"ok": true}`
- `POST /api/scan` body `ScanRequest` → `session.scan`
- `GET/PUT /api/config` → `get_config` / `put_config`（PUT 只更新 `ConfigUpdate` 中非 `None` 字段，再 `save_local_config`）
- `GET /api/ffmpeg-status` → `{available: bool, message: str}` 使用 `find_ffmpeg` / `ffmpeg_missing_message` / `describe_ffmpeg_status`
- `POST /api/convert` → `session.start_convert`；若已在跑 → HTTP 409
- `POST /api/cancel` → `cancel_all`
- `POST /api/cancel/{task_id}` → `cancel_task`；未知 id → 404
- `GET /api/batch` → `batch_snapshot`
- `WebSocket /ws`：subscribe → 循环 `q.get()` 并 `send_json`；断开时 unsubscribe。用 `asyncio.to_thread(q.get)` 或短轮询 `get_nowait` + `asyncio.sleep(0.05)` 避免阻塞事件循环。

`sidecar/__main__.py`：

```python
from __future__ import annotations

import os

import uvicorn

from sidecar.app import create_app


def main() -> None:
    host = '127.0.0.1'
    port = int(os.environ.get('M3U8_SIDECAR_PORT', '0'))
    uvicorn.run(create_app(), host=host, port=port, log_level='info')


if __name__ == '__main__':
    main()
```

注意：`port=0` 时 uvicorn 会选端口；若打印不便，可在本阶段改默认开发端口 `8765`（环境变量仍可覆盖）。**开发默认端口定为 `8765`**：`int(os.environ.get('M3U8_SIDECAR_PORT', '8765'))`。

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_sidecar_api -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add sidecar/app.py sidecar/__main__.py tests/test_sidecar_api.py
git commit -m "feat: expose sidecar REST API for health config and batch"
```

---

### Task 5: Convert + cancel + WebSocket 事件联调测试

**Files:**
- Modify: `sidecar/session.py`（若 Task 3 未完成 convert 线程）
- Test: `tests/test_sidecar_ws.py`

**Interfaces:**
- Consumes: Task 3/4 的 `create_app` / `SidecarSession`
- Produces: WS 事件 `type` 集合：`task_started`、`task_progress`、`task_done`、`task_error`、`task_skipped`、`batch_progress`、`batch_finished`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sidecar_ws.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.models import ConversionTask, TaskStatus
from sidecar.app import create_app
from sidecar.session import SidecarSession


class SidecarWsTests(unittest.TestCase):
    def test_convert_emits_batch_finished(self) -> None:
        session = SidecarSession()
        client = TestClient(create_app(session))

        def fake_convert(self, stream_index=None, progress_callback=None, cancel_event=None):
            if progress_callback:
                progress_callback('merging', 1, 1)
                progress_callback('packaging', 1, 1)

        with patch('core.batch_convert.M3U8Converter.convert', new=fake_convert):
            with client.websocket_connect('/ws') as ws:
                res = client.post(
                    '/api/convert',
                    json={'tasks': [{'task_id': 't1', 'path': 'C:/fake/index.m3u8', 'selected_stream_index': 0}]},
                )
                self.assertEqual(res.status_code, 200)
                types = []
                for _ in range(20):
                    msg = ws.receive_json()
                    types.append(msg['type'])
                    if msg['type'] == 'batch_finished':
                        break
                self.assertIn('batch_finished', types)


if __name__ == '__main__':
    unittest.main()
```

实现注意：`start_convert` 需能接受任意 path 字符串并构造 `ConversionTask(entry=M3u8Entry(path=Path(...), streams=[]))`，**不要**在 convert 路径上再次 `from_path` 解析（解析已在 scan 完成）。若 `M3U8Converter` 被 mock，path 可不存在。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sidecar_ws -v`  
Expected: FAIL（convert/WS 未接通）直到实现完成

- [ ] **Step 3: Finish convert thread + cancel endpoints behavior**

- `POST /api/cancel` 在空闲时返回 200（幂等）
- `POST /api/cancel/{task_id}` 在批次中找不到 id 返回 404
- 单测可再加：`cancel_all` 时 mock 长任务，断言后续任务 `SKIPPED`／当前 `ERROR`（与现 batch 语义一致）——若时间紧，至少保留 `batch_finished` 测试

- [ ] **Step 4: Run all sidecar tests + core regression**

```powershell
python -m unittest tests.test_sidecar_events tests.test_sidecar_session tests.test_sidecar_api tests.test_sidecar_ws tests.test_batch_convert -v
```

Expected: PASS

- [ ] **Step 5: Manual smoke（可选但推荐）**

```powershell
$env:M3U8_SIDECAR_PORT = '8765'
python -m sidecar
# 另一终端
curl http://127.0.0.1:8765/api/health
```

Expected: `{"ok":true}`

- [ ] **Step 6: Commit**

```powershell
git add sidecar tests/test_sidecar_ws.py
git commit -m "feat: stream conversion events over sidecar websocket"
```

---

## Phase 1 Done 标准

- `python -m sidecar` 可启动
- REST/WS 测试通过
- 现有 batch/worker 单测仍通过
- 无 Tauri/React 也可演示 API

进入 Phase 2 计划：`docs/superpowers/plans/2026-07-18-tauri-react-sidecar-phase2-ui.md`

# Tauri React Sidecar — Phase 3: Tauri 壳、打包、移除旧 GUI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Tauri 2 承载 React UI，启动并监督 Python sidecar，接入原生拖放/文件对话框，产出 Windows 发行包，并移除 CustomTkinter GUI 入口。

**Architecture:** Tauri 在 setup 时分配/固定 sidecar 端口，spawn `m3u8-sidecar`（开发时用 `python -m sidecar`），把 `http://127.0.0.1:<port>` 注入前端；打包时 PyInstaller 打 sidecar exe，Tauri externalBin 拉起。CLI `main.py` 保留。

**Tech Stack:** Tauri 2、Rust（最少）、Phase 1/2 产物、PyInstaller、Windows

**Spec:** `docs/superpowers/specs/2026-07-18-tauri-react-sidecar-design.md`  
**Depends on:** Phase 1 + Phase 2

**Plan series:** 1 API → 2 UI → **3 Shell（本文件）**

## Global Constraints

- Sidecar 仅 `127.0.0.1`
- 开发：`beforeDevCommand` 起 Vite；sidecar 由 Rust 侧或 `beforeDevCommand` 脚本拉起
- 发行：用户无需系统 Python；FFmpeg 经 `imageio-ffmpeg` 打入 sidecar
- 删除产品级 CustomTkinter 入口；`core/` + CLI 保留
- 测试：既有 unittest + `ui` vitest；壳层以手工验收为主
- Windows PowerShell 提交

---

## File Structure

| File | Responsibility |
|------|----------------|
| Create: `src-tauri/`（`cargo tauri` 生成） | 桌面壳 |
| Modify: `src-tauri/tauri.conf.json` | 窗口、sidecar、构建命令 |
| Modify: `src-tauri/src/lib.rs` 或 `main.rs` | 启动 sidecar、注入端口、对话框命令 |
| Create: `src-tauri/binaries/` 或构建输出目录 | sidecar 二进制占位说明 |
| Create: `sidecar/build_sidecar.spec` | PyInstaller 打 sidecar |
| Create: `scripts/dev.ps1`、`scripts/build.ps1` | 开发/发行脚本 |
| Modify: `ui/src/api/*`、`DropZone`、`App.tsx` | Tauri 路径/拖放/对话框 |
| Modify: `README.md`、`build.bat` | 文档与入口 |
| Modify: `requirements.txt` | 移除 customtkinter/tkinterdnd2（若无残留引用） |
| Delete: `gui_app.py`、`gui/`（整包）、旧 `build.spec` GUI 入口 | 退役 Tk GUI |
| Modify: `main.py` | 确认仅依赖 `core.models` |
| Create: `tests/test_no_gui_import_in_core.py` | core/sidecar 不依赖 customtkinter |

---

### Task 1: 初始化 Tauri 2 工程并挂上 `ui/`

**Files:**
- Create: `src-tauri/**`
- Modify: `ui/vite.config.ts`（如需 `strictPort`）
- Modify: 根目录或 `ui/package.json` 增加 `@tauri-apps/cli` / `@tauri-apps/api`

**Interfaces:**
- Produces: `npm run tauri dev`（或根脚本）能打开空壳加载 React 页

- [ ] **Step 1: Install Tauri CLI tooling**

前置：已装 Rust stable、WebView2（Win10 通常已有）。

```powershell
cd ui
npm install -D @tauri-apps/cli
npm install @tauri-apps/api @tauri-apps/plugin-dialog @tauri-apps/plugin-shell @tauri-apps/plugin-fs
npx tauri init
```

交互选项（非交互时改生成文件）：

- App name: `m3u8-to-mp4`
- Window title: `m3u8 → mp4`
- Frontend dist: `../ui/dist`（若 init 在 `ui` 内则为 `../dist`——**推荐在仓库根执行 init**，frontendDir=`ui`）

若 `tauri init` 在 `ui/` 下生成 `ui/src-tauri`，则 **移动** 为仓库根 `src-tauri/`，并修正 `tauri.conf.json` 中路径：

- `build.frontendDist`: `../ui/dist`
- `build.devUrl`: `http://127.0.0.1:5173`
- `build.beforeDevCommand`: `npm --prefix ui run dev`
- `build.beforeBuildCommand`: `npm --prefix ui run build`

- [ ] **Step 2: Window defaults**

`tauri.conf.json`：

```json
{
  "productName": "m3u8-to-mp4",
  "identifier": "com.m3u8tomp4.app",
  "app": {
    "windows": [
      {
        "title": "m3u8 → mp4",
        "width": 900,
        "height": 700,
        "minWidth": 760,
        "minHeight": 560
      }
    ]
  }
}
```

（字段名以 Tauri 2 实际 schema 为准，生成后对照改。）

- [ ] **Step 3: Smoke**

```powershell
cd ui
npx tauri dev
```

Expected: 桌面窗口加载 React UI（sidecar 可暂未接）。

- [ ] **Step 4: Commit**

```powershell
git add src-tauri ui/package.json ui/package-lock.json
git commit -m "chore: initialize Tauri 2 shell for React UI"
```

---

### Task 2: 启动 sidecar 与 health 门闩

**Files:**
- Modify: `src-tauri/src/lib.rs`（或 `main.rs`）
- Modify: `src-tauri/capabilities/*.json`（允许 shell sidecar）
- Modify: `ui/src/App.tsx`、`ui/src/api/client.ts`
- Create: `scripts/dev.ps1`

**Interfaces:**
- Produces:
  - Rust 启动时设置 env `M3U8_SIDECAR_PORT=8765`（开发固定；发行可同）
  - 开发：`Command::new("python").args(["-m", "sidecar"])` 在 app 根目录 spawn，stdin null，create_no_window
  - 前端等待 `GET /api/health` 成功再渲染主队列；失败显示「重试」
  - App 退出时 kill sidecar 子进程

- [ ] **Step 1: Dev spawn logic（Rust）**

伪代码（写入实际 Rust）：

```rust
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

struct SidecarState(Mutex<Option<Child>>);

fn start_sidecar(app_handle: &tauri::AppHandle) -> Result<(), String> {
  let mut child = Command::new("python")
    .args(["-m", "sidecar"])
    .env("M3U8_SIDECAR_PORT", "8765")
    .current_dir(repo_root()) // 开发：manifest 旁向上找到含 sidecar/ 的目录
    .stdout(Stdio::null())
    .stderr(Stdio::null())
    .spawn()
    .map_err(|e| e.to_string())?;
  // 存入 managed state
  Ok(())
}
```

发行模式：`Command::new(sidecar_sidecar_path())` 使用 Tauri `external_bin` 名称 `m3u8-sidecar`。

- [ ] **Step 2: Frontend base URL**

开发期继续用 Vite proxy（相对路径 `/api`）。  
Tauri 生产加载 `tauri://` / `asset` 时 **没有** Vite 代理：在 `ui` 构建时用 env：

```ts
const BASE = import.meta.env.VITE_SIDECAR_BASE ?? ''
// fetch(`${BASE}/api/health`)
```

生产由 Tauri 在创建窗口前注入：`VITE_SIDECAR_BASE=http://127.0.0.1:8765` 打进 build，或通过 `invoke('get_sidecar_base')` 返回 base URL（**推荐 invoke**，避免写死）：

```ts
import { invoke } from '@tauri-apps/api/core'
const base = await invoke<string>('get_sidecar_base')
```

`client.ts` 改为 `createApi(base)`。

- [ ] **Step 3: Gate UI on health**

`App` 启动：`invoke start` 后轮询 health 最多 ~10s；失败展示错误页按钮「重试」。

- [ ] **Step 4: Manual**

```powershell
npx tauri dev
```

Expected: 窗口打开后自动可用 scan（无需另开 sidecar 终端）。

- [ ] **Step 5: Commit**

```powershell
git add src-tauri ui/src scripts/dev.ps1
git commit -m "feat: spawn python sidecar from Tauri with health gate"
```

---

### Task 3: 原生文件对话框与拖放路径

**Files:**
- Modify: `ui/src/components/DropZone.tsx`
- Modify: `ui/src/components/OutputBar.tsx`
- Modify: `src-tauri/capabilities`（fs/dialog/dnd 权限）
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Produces:
  - 「选择文件/文件夹」→ `@tauri-apps/plugin-dialog` → `string[]` paths → `api.scan`
  - 窗口拖放：使用 Tauri 拖放事件拿到路径列表（非浏览器 File 假路径）
  - 输出目录选择：dialog `directory: true`

- [ ] **Step 1: Dialog buttons**

```ts
import { open } from '@tauri-apps/plugin-dialog'

export async function pickM3u8Files(): Promise<string[]> {
  const selected = await open({
    multiple: true,
    filters: [{ name: 'm3u8', extensions: ['m3u8'] }],
  })
  if (selected === null) return []
  return Array.isArray(selected) ? selected : [selected]
}

export async function pickDirectory(): Promise<string | null> {
  const selected = await open({ directory: true, multiple: false })
  return typeof selected === 'string' ? selected : null
}
```

- [ ] **Step 2: Drag-drop**

按 Tauri 2 文档注册窗口拖放（`onDragDropEvent` / 插件 API，以当前版本文档为准），将 `paths` 交给现有 `addPaths` handler。移除 Phase 2「仅多行粘贴」为唯一入口，可保留为高级后备。

- [ ] **Step 3: Manual acceptance**

拖入文件夹、选文件、选输出目录，行为与旧 GUI 一致。

- [ ] **Step 4: Commit**

```powershell
git add ui/src src-tauri
git commit -m "feat: use Tauri dialogs and drag-drop for real paths"
```

---

### Task 4: PyInstaller sidecar + Tauri externalBin

**Files:**
- Create: `sidecar/build_sidecar.spec`
- Create: `scripts/build.ps1`
- Modify: `src-tauri/tauri.conf.json`（`bundle.externalBin`）
- Modify: `build.bat` 改为调用 `scripts/build.ps1`
- Create: `sidecar/__main__.py` 若尚未保证 frozen 友好（`sys.frozen` 时工作目录）

**Interfaces:**
- Produces: `dist/m3u8-sidecar.exe`（console=False 或 True 以便排障；**发行用 console=False**）
- Tauri bundle 含 sidecar 与主程序

- [ ] **Step 1: Spec file**

`sidecar/build_sidecar.spec` 以现 `build.spec` 为模板，但：

- `Analysis(['sidecar/__main__.py'], ...)` 或小入口 `sidecar_app.py` 调 `sidecar.__main__.main`
- `datas` 含 `config.yaml` + `imageio_ffmpeg` collect_all
- **不要** collect customtkinter / tkinterdnd2
- `name='m3u8-sidecar'`
- `console=False`

- [ ] **Step 2: Build sidecar**

```powershell
pyinstaller sidecar/build_sidecar.spec --noconfirm
```

Expected: `dist/m3u8-sidecar.exe` 存在；运行后监听 8765（需设 env）。

手工：`curl http://127.0.0.1:8765/api/health`

- [ ] **Step 3: Wire externalBin**

Tauri 2 externalBin 要求二进制命名带 target triple，例如：

`src-tauri/binaries/m3u8-sidecar-x86_64-pc-windows-msvc.exe`

`scripts/build.ps1`：

1. `pyinstaller ...`
2. copy 到 `src-tauri/binaries/` 正确文件名
3. `npm --prefix ui run build`
4. `npx tauri build`

- [ ] **Step 4: Commit**

```powershell
git add sidecar/build_sidecar.spec scripts/build.ps1 build.bat src-tauri/tauri.conf.json
git commit -m "build: package python sidecar for Tauri externalBin"
```

（不要提交巨大 exe；`.gitignore` 忽略 `src-tauri/binaries/*.exe` 与 `dist/`。）

---

### Task 5: 移除 CustomTkinter GUI 并更新文档

**Files:**
- Delete: `gui_app.py`、`gui/` 目录、旧 GUI 专用测试中对 Tk 的依赖（`tests/test_worker_*` 若只测 worker：把 `gui/worker.py` **迁到** `sidecar/worker_bridge.py` 或 `core/worker_events.py` 再删 `gui/`）
- Modify: `requirements.txt`、`README.md`、`build.bat`
- Test: `tests/test_no_gui_import_in_core.py`
- Modify: 所有仍 `from gui.` 的模块

**关键依赖清理顺序：**

1. 将 `gui/worker.py` 的 `map_task_progress` +（若 sidecar 已内联则不必迁整个 ConversionWorker）确保 sidecar 不再 import `gui.*`
2. `queue_messages` 已在 Phase 1 到 `core/`
3. 删除 `gui/`、`gui_app.py`
4. 更新/删除仅 GUI 的测试；保留 `test_batch_convert` 等

- [ ] **Step 1: Write guard test**

```python
# tests/test_no_gui_import_in_core.py
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NoGuiImportTests(unittest.TestCase):
    def test_core_and_sidecar_avoid_gui_and_ctk(self) -> None:
        banned = ('gui', 'customtkinter', 'tkinterdnd2')
        for package in ('core', 'sidecar'):
            for path in (ROOT / package).rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertFalse(
                                any(alias.name == b or alias.name.startswith(b + '.') for b in banned),
                                msg=f'{path} imports {alias.name}',
                            )
                    if isinstance(node, ast.ImportFrom) and node.module:
                        self.assertFalse(
                            any(node.module == b or node.module.startswith(b + '.') for b in banned),
                            msg=f'{path} imports from {node.module}',
                        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run to find remaining imports**

```powershell
python -m unittest tests.test_no_gui_import_in_core -v
```

按报错清理，直到 PASS；再删 `gui/`。

- [ ] **Step 3: README**

替换桌面启动说明：

- 开发：`scripts/dev.ps1` 或 `npx tauri dev`
- 发行：`scripts/build.ps1` / `build.bat`
- CLI：`python main.py ...` 不变

- [ ] **Step 4: Full regression**

```powershell
python -m unittest discover -s tests -v
cd ui
npm test
```

Expected: PASS（删除过时 GUI 测试后）

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "refactor: remove CustomTkinter GUI in favor of Tauri app"
```

---

### Task 6: 发行验收清单

**Files:** 无代码；更新 README「验收」小节可选

- [ ] **Step 1: 干净机器/新目录跑打包产物**

验收项（全部勾选才算 Phase 3 完成）：

1. 双击/运行 Tauri 主程序，无系统 Python 也可出窗口  
2. sidecar 自动起来，health 通过  
3. 拖放 m3u8 / 选文件夹导入  
4. 设置并行数并持久化到 `local_config.yaml`  
5. 开始转换，进度平滑，无整表闪烁  
6. 行内取消与取消全部  
7. 失败任务可展开/复制  
8. FFmpeg 缺失时有明确提示  
9. `python main.py` CLI 仍可用（开发环境）

- [ ] **Step 2: Final commit if docs tweaked**

```powershell
git add README.md
git commit -m "docs: document Tauri desktop build and usage"
```

---

## Phase 3 / 全系列 Done 标准

- Spec 成功标准全部满足
- 旧 Tk GUI 不再作为产品入口
- 三份计划中的测试命令均可通过

---

## Spec Coverage（系列自检）

| Spec 项 | Plan Task |
|---------|-----------|
| 模型不绑 GUI / 复用 core | P1 T1–T3 |
| REST + WS API | P1 T4–T5 |
| React 队列 + 增量更新 | P2 T2–T3 |
| 动效 | P2 T4 |
| Tauri 壳 + sidecar 生命周期 | P3 T1–T2 |
| 原生拖放/对话框 | P3 T3 |
| 打包 FFmpeg sidecar | P3 T4 |
| 移除 CustomTkinter | P3 T5 |
| 验收 | P3 T6 |

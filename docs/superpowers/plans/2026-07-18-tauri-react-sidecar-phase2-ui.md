# Tauri React Sidecar — Phase 2: React 队列 UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Vite + React + TypeScript 实现与现 GUI 对等的单页转换队列，经 REST/WS 连接 Phase 1 sidecar，并加入克制列表/进度动效。

**Architecture:** React 持有任务列表与勾选态；sidecar 只在 convert 期间执行；`task_id` 由前端在加入队列时用 `crypto.randomUUID()` 生成。开发期用浏览器打开 Vite，代理到 `http://127.0.0.1:8765`。

**Tech Stack:** Vite 6、React 19、TypeScript、Framer Motion、Vitest、Phase 1 sidecar

**Spec:** `docs/superpowers/specs/2026-07-18-tauri-react-sidecar-design.md`  
**Depends on:** Phase 1 完成（`python -m sidecar` + API 可用）

**Plan series:** 1 API → **2 UI（本文件）** → 3 Shell

## Global Constraints

- 单一工作区队列（不对标多仪表盘）
- 进度事件只 patch 对应 `task_id` 行，禁止因进度重建整个列表
- 视觉语义色对齐现 `gui/theme.py`（CSS 变量）
- 动效仅：列表进出、进度条、设置模态
- 测试：`npm test`（Vitest）；sidecar 仍用 `python -m unittest`
- Windows PowerShell 提交

---

## File Structure

| File | Responsibility |
|------|----------------|
| Create: `ui/package.json` | 前端依赖与脚本 |
| Create: `ui/vite.config.ts` | Vite + 代理 `/api` `/ws` |
| Create: `ui/tsconfig.json`、`ui/index.html` | TS/HTML 入口 |
| Create: `ui/src/main.tsx`、`ui/src/App.tsx` | 应用根 |
| Create: `ui/src/styles/tokens.css` | 设计令牌 |
| Create: `ui/src/api/client.ts` | REST 封装 |
| Create: `ui/src/api/ws.ts` | WebSocket 客户端 |
| Create: `ui/src/types.ts` | 共享 TS 类型 |
| Create: `ui/src/state/queueStore.ts` | 队列状态（含 reducer） |
| Create: `ui/src/components/*` | TopBar、OutputBar、Toolbar、DropZone、TaskList、TaskRow、SettingsModal |
| Create: `ui/src/state/queueStore.test.ts` | 状态机单测 |
| Create: `ui/README.md` | 本地启动说明 |

---

### Task 1: 脚手架 Vite React TS 工程

**Files:**
- Create: `ui/package.json`、`ui/vite.config.ts`、`ui/tsconfig.json`、`ui/tsconfig.app.json`、`ui/index.html`、`ui/src/main.tsx`、`ui/src/App.tsx`、`ui/src/vite-env.d.ts`

**Interfaces:**
- Produces: `npm run dev` 可在 `http://127.0.0.1:5173` 打开占位页
- Vite proxy: `/api` → `http://127.0.0.1:8765`，`/ws` → `ws://127.0.0.1:8765`

- [ ] **Step 1: Scaffold**

在仓库根目录执行（不要手写残缺 package 若可用 CLI）：

```powershell
npm create vite@latest ui -- --template react-ts
cd ui
npm install
npm install framer-motion
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 2: Configure Vitest + proxy**

`ui/vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

`ui/package.json` scripts 增加：`"test": "vitest run"`、`"test:watch": "vitest"`

- [ ] **Step 3: Replace App placeholder**

`App.tsx` 临时渲染 `<main>m3u8 → mp4</main>`。

- [ ] **Step 4: Verify**

```powershell
cd ui
npm run dev
```

Expected: 浏览器可打开标题页。Ctrl+C 结束。

- [ ] **Step 5: Commit**

```powershell
git add ui
git commit -m "chore: scaffold Vite React UI for desktop queue"
```

---

### Task 2: 类型、API client、队列 reducer

**Files:**
- Create: `ui/src/types.ts`
- Create: `ui/src/api/client.ts`
- Create: `ui/src/api/ws.ts`
- Create: `ui/src/state/queueStore.ts`
- Test: `ui/src/state/queueStore.test.ts`

**Interfaces:**
- Produces:
  - `type TaskStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped'`
  - `interface QueueTask { id: string; path: string; name: string; directory: string; selected: boolean; isMasterPlaylist: boolean; streamLabels: string[]; selectedStreamIndex: number; status: TaskStatus; errorMessage: string; progressPercent: number | null; progressPhase: string; progressMessage: string; errorExpanded: boolean }`
  - `function queueReducer(state, action): QueueState`
  - Actions 至少：`HYDRATE_CONFIG`、`ADD_ENTRIES`、`TOGGLE_TASK`、`SET_STREAM`、`SELECT_ALL`、`CLEAR`、`START_BATCH`、`PATCH_TASK`、`BATCH_FINISHED`、`SET_FEEDBACK`、`SET_CONVERTING`

- [ ] **Step 1: Write the failing test**

```ts
// ui/src/state/queueStore.test.ts
import { describe, expect, it } from 'vitest'
import { initialQueueState, queueReducer, type QueueTask } from './queueStore'

function task(partial: Partial<QueueTask> & Pick<QueueTask, 'id' | 'path'>): QueueTask {
  return {
    name: 'index.m3u8',
    directory: 'C:/v',
    selected: true,
    isMasterPlaylist: false,
    streamLabels: [],
    selectedStreamIndex: 0,
    status: 'pending',
    errorMessage: '',
    progressPercent: null,
    progressPhase: '',
    progressMessage: '',
    errorExpanded: false,
    ...partial,
  }
}

describe('queueReducer', () => {
  it('adds entries with stable ids and dedupes by path', () => {
    const a = task({ id: '1', path: 'C:/a/index.m3u8' })
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [a],
      feedback: 'ok',
    })
    state = queueReducer(state, {
      type: 'ADD_ENTRIES',
      entries: [task({ id: '2', path: 'C:/a/index.m3u8' })],
      feedback: 'dup',
    })
    expect(state.tasks).toHaveLength(1)
    expect(state.tasks[0].id).toBe('1')
  })

  it('patches a single task by id without replacing others', () => {
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [task({ id: '1', path: 'C:/a/index.m3u8' }), task({ id: '2', path: 'C:/b/index.m3u8' })],
      feedback: '',
    })
    const beforeSecond = state.tasks[1]
    state = queueReducer(state, {
      type: 'PATCH_TASK',
      taskId: '1',
      patch: { status: 'running', progressPercent: 40 },
    })
    expect(state.tasks[0].progressPercent).toBe(40)
    expect(state.tasks[1]).toBe(beforeSecond)
  })

  it('freezes selected ids on START_BATCH', () => {
    let state = queueReducer(initialQueueState, {
      type: 'ADD_ENTRIES',
      entries: [
        task({ id: '1', path: 'C:/a/index.m3u8', selected: true }),
        task({ id: '2', path: 'C:/b/index.m3u8', selected: false }),
      ],
      feedback: '',
    })
    state = queueReducer(state, { type: 'START_BATCH' })
    expect(state.isConverting).toBe(true)
    expect(state.activeBatchIds).toEqual(['1'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
cd ui
npm test
```

Expected: FAIL — modules missing

- [ ] **Step 3: Implement types + reducer + API helpers**

`ui/src/api/client.ts` 示例：

```ts
async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    throw new Error(`${res.status} ${await res.text()}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => json<{ ok: boolean }>('/api/health'),
  getConfig: () => json<Record<string, unknown>>('/api/config'),
  putConfig: (body: Record<string, unknown>) =>
    json<Record<string, unknown>>('/api/config', { method: 'PUT', body: JSON.stringify(body) }),
  scan: (paths: string[], knownPaths: string[]) =>
    json<{
      entries: Array<{
        path: string
        is_master_playlist: boolean
        stream_labels: string[]
        selected_stream_index: number
      }>
      added: number
      duplicates: number
      unparseable: number
      message: string
    }>('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ paths, known_paths: knownPaths }),
    }),
  convert: (tasks: Array<{ task_id: string; path: string; selected_stream_index: number }>) =>
    json<{ ok: boolean }>('/api/convert', { method: 'POST', body: JSON.stringify({ tasks }) }),
  cancelAll: () => json<{ ok: boolean }>('/api/cancel', { method: 'POST', body: '{}' }),
  cancelTask: (taskId: string) =>
    json<{ ok: boolean }>(`/api/cancel/${encodeURIComponent(taskId)}`, { method: 'POST', body: '{}' }),
  batch: () => json<{ is_converting: boolean; tasks: unknown[] }>('/api/batch'),
  ffmpegStatus: () => json<{ available: boolean; message: string }>('/api/ffmpeg-status'),
}
```

`ui/src/api/ws.ts`：连接 `const proto = location.protocol === 'https:' ? 'wss' : 'ws'; new WebSocket(`${proto}://${location.host}/ws`)`；`onmessage` JSON.parse 后回调；提供 `connect`/`disconnect`/`onEvent`。

`queueStore.ts`：实现 `initialQueueState` 与 `queueReducer`；`ADD_ENTRIES` 按 `path` 去重；`CLEAR` 在 `isConverting` 时为 no-op。

- [ ] **Step 4: Run test**

```powershell
cd ui
npm test
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add ui/src
git commit -m "feat: add queue reducer and sidecar API client"
```

---

### Task 3: 主界面组件（静态 + 接线）

**Files:**
- Create: `ui/src/styles/tokens.css`
- Create: `ui/src/components/TopBar.tsx`
- Create: `ui/src/components/OutputBar.tsx`
- Create: `ui/src/components/Toolbar.tsx`
- Create: `ui/src/components/DropZone.tsx`
- Create: `ui/src/components/TaskRow.tsx`
- Create: `ui/src/components/TaskList.tsx`
- Create: `ui/src/components/SettingsModal.tsx`
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Consumes: `api`、`queueReducer`、`connectWs`
- Produces: 功能对等主界面（浏览器内用 `<input type="file" webkitdirectory multiple>` 选文件；完整系统拖放路径留给 Phase 3 Tauri）

- [ ] **Step 1: Add CSS tokens**

`tokens.css` 定义（与 theme 对齐）：

```css
:root {
  --surface-bg: #f8fafc;
  --surface-card: #ffffff;
  --surface-muted: #f1f5f9;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --border: #e2e8f0;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --success: #15803d;
  --error: #dc2626;
  --warning: #d97706;
  --radius-sm: 6px;
  --radius-md: 8px;
  --font-ui: "Microsoft YaHei UI", "PingFang SC", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-bg: #0f172a;
    --surface-card: #162033;
    --surface-muted: #1e293b;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --border: #334155;
  }
}
```

- [ ] **Step 2: Build layout components**

`App.tsx` 状态：`useReducer(queueReducer, initialQueueState)`；挂载时 `api.health`、`api.getConfig`、`api.ffmpegStatus`；`useEffect` 连接 WS，将事件映射为 `PATCH_TASK` / `BATCH_FINISHED` / feedback。

按钮可用性对齐现逻辑：

- 全选/清空：有任务且非 converting
- 开始：有选中且非 converting 且 ffmpeg available
- 取消全部：converting 时显示

`DropZone`：在浏览器阶段用 file input；读取 `File.path` **仅在 Tauri 可用**——Phase 2 先支持「粘贴路径文本框」或开发用 JSON 列表输入作为后备，并在 UI 标注「桌面版将支持拖放」。更干净的做法：提供路径输入（多行）调用 `api.scan`，Phase 3 再接原生拖放。**采用多行路径输入 + 选择文件夹（Tauri 未接入前用 input）**。

设置模态：编辑 config 字段，保存 `api.putConfig`。

- [ ] **Step 3: Manual wiring check**

终端 1：

```powershell
$env:M3U8_SIDECAR_PORT = '8765'
python -m sidecar
```

终端 2：

```powershell
cd ui
npm run dev
```

手工：粘贴一个含 m3u8 的目录路径 → 出现任务行 → 打开设置改并行数 → 保存后 GET config 一致。

- [ ] **Step 4: Commit**

```powershell
git add ui
git commit -m "feat: build React conversion queue UI wired to sidecar"
```

---

### Task 4: Framer Motion 动效

**Files:**
- Modify: `ui/src/components/TaskList.tsx`
- Modify: `ui/src/components/TaskRow.tsx`
- Modify: `ui/src/components/SettingsModal.tsx`

**Interfaces:**
- Produces: 列表 `AnimatePresence`；进度条 CSS `transition: width 160ms linear`；设置模态 opacity/y 过渡

- [ ] **Step 1: List animation**

```tsx
import { AnimatePresence, motion } from 'framer-motion'

// TaskList 内：
<AnimatePresence initial={false}>
  {tasks.map((task) => (
    <motion.div
      key={task.id}
      layout
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.18 }}
    >
      <TaskRow task={task} ... />
    </motion.div>
  ))}
</AnimatePresence>
```

- [ ] **Step 2: Progress + modal**

进度条：`style={{ width: `${percent}%`, transition: 'width 160ms linear' }}`  
SettingsModal：`motion.div` 蒙层 + 面板 `initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}`

- [ ] **Step 3: Visual check**

导入/删除任务应有过渡；转换进度条平滑；无整表闪白。

- [ ] **Step 4: Commit**

```powershell
git add ui/src/components
git commit -m "feat: add restrained motion to queue and settings"
```

---

### Task 5: 转换流程端到端（浏览器 + sidecar）

**Files:**
- Modify: `ui/src/App.tsx`（开始/取消/批次反馈）
- Create: `ui/README.md`

- [ ] **Step 1: Wire start/cancel**

开始：

1. `dispatch({ type: 'START_BATCH' })`
2. `api.convert(activeTasks.map(...))`
3. WS 更新行状态
4. `batch_finished` → 汇总 feedback（成功/失败/取消计数，逻辑对齐 `gui.task_list.batch_feedback`）

取消全部 / 行内取消：调对应 API；按钮文案「正在取消…」在本地 flag 控制。

WS 重连：`onclose` 后延迟重连，并 `api.batch()` 合并快照到 `PATCH_TASK`。

- [ ] **Step 2: Document**

`ui/README.md` 写明：

```markdown
# UI 开发

1. 启动 sidecar：`M3U8_SIDECAR_PORT=8765 python -m sidecar`
2. `npm install` / `npm run dev`
3. 浏览器打开 http://127.0.0.1:5173
```

- [ ] **Step 3: Regression**

```powershell
cd ui
npm test
python -m unittest tests.test_sidecar_api tests.test_sidecar_ws -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```powershell
git add ui
git commit -m "feat: complete browser queue convert cancel flow"
```

---

## Phase 2 Done 标准

- 浏览器内可完成：导入（路径）、设置、开始、进度、取消、错误展开
- 列表增量更新 + 基础动效
- 系统级拖放/原生文件对话框留到 Phase 3

进入 Phase 3：`docs/superpowers/plans/2026-07-18-tauri-react-sidecar-phase3-shell.md`

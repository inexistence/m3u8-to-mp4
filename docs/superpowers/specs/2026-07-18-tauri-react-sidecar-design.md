# Tauri 2 + React + Python Sidecar 桌面体验重做

日期：2026-07-18  
状态：已批准

## 背景

当前 Windows GUI 基于 CustomTkinter + Tk。任务列表在 `set_tasks` 时整表 `destroy` 再重建，进度刷新依赖反复配置控件，且 Tk 几乎无法做流畅过渡，导致「无动画、刷新卡顿」的体感。业务核心（`core/`、批量转换、取消）已可用，问题集中在桌面壳与 UI 渲染层。

## 目标

- 用 **Tauri 2 + React (Vite + TypeScript)** 完整替换 CustomTkinter GUI，功能与现有桌面应用对等
- Python 转换逻辑以 **sidecar 进程** 暴露本地 API，复用 `core/`、`batch_convert`、取消控制器；**CLI（`main.py`）保持可用**
- 进度与状态通过事件 **增量更新** 单行 UI，配合克制动效，消除整表重建带来的卡顿
- 发行版仍为 Windows 可分发应用：主程序 + sidecar + FFmpeg 资源，用户无需自备 Python

## 非目标

- 不把转换核心重写为 Rust
- 不引入 Electron
- 不做花哨全页动效或多仪表盘信息架构
- 不在本期做跨平台发行（设计按 Windows 落地；架构不故意堵死后续）
- 不改变 CLI 的使用方式与配置语义

## 选定方案

**方案 1：Tauri 壳 + React 队列态 + Python Sidecar（REST + WebSocket）**

备选（已否决）：

- Python 为唯一状态源、React 薄视图：交互延迟与乐观更新更差
- 仅 CLI 子进程包装：并行进度与单任务取消难以对等

## 设计

### 1. 架构与模块边界

```text
┌─────────────────────────────────────────────┐
│  Tauri 2 桌面壳                              │
│  · 窗口 / 系统拖放 / 原生文件对话框           │
│  · 启动 & 监督 Python sidecar               │
│  · 打包：主程序 + sidecar + FFmpeg 资源      │
└──────────────────┬──────────────────────────┘
                   │  localhost（仅本机）
┌──────────────────▼──────────────────────────┐
│  React (Vite + TS)                           │
│  · 队列 UI、设置、动画与过渡                  │
│  · 任务列表展示态（选中、展开错误）           │
│  · REST 发命令，WebSocket 收进度事件         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Python Sidecar（FastAPI）                   │
│  · REST：scan / convert / cancel / config    │
│  · WebSocket：推送与 WorkerEvent 等价的事件  │
│  · 读/写 local_config.yaml                   │
│  · 复用 core/、batch_convert、取消逻辑       │
└─────────────────────────────────────────────┘
```

| 模块 | 负责 | 不负责 |
|------|------|--------|
| `core/` + CLI | 发现、解密、合片、FFmpeg、批量转换 | UI、HTTP |
| Sidecar | 将 worker/配置能力暴露为本地 API | 渲染、动画 |
| React | 交互、观感、队列展示态 | 直接跑 FFmpeg |
| Tauri | 进程生命周期、原生能力、分发 | 业务规则 |

**替换范围**：CustomTkinter GUI（`gui/`、`gui_app.py`）退役；应用主入口改为 Tauri。`main.py` 与 `core/` 保留。

**仓库布局（建议）**

- `src-tauri/` — Tauri / Rust 壳
- `ui/` — React 前端
- `sidecar/` — Python HTTP/WS 服务（薄封装，调用现有 `core` 与批处理）
- 现有 `core/`、`main.py`、`tests/` 位置不变

### 2. 状态归属

| 状态 | 归属 | 说明 |
|------|------|------|
| 任务列表、勾选、码率选择、错误展开 | React | 本地即时更新，带动画 |
| 输出目录、并行数、文件名规则等配置 | Sidecar 持久化；React 持编辑副本 | 保存时写入 API |
| 转换执行、取消令牌、真实进度 | Sidecar | 对齐现有 `ConversionWorker` 行为 |
| 窗口与系统拖放得到的路径 | Tauri → React | React 再调用 scan |

**任务身份**：每条任务使用稳定 `task_id`（UUID）。扫描返回、提交转换、取消与 WS 事件全程使用同一 id，**禁止**用易变的列表下标作为跨进程身份。

**批次行为（与现 GUI 一致）**：点击「开始转换」时冻结当前已选任务为本批；运行期间允许继续导入，新增任务只进入下一批。

### 3. API 与事件流

#### REST（命令）

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/api/health` | Sidecar 就绪探测（Tauri 启动轮询） |
| `POST` | `/api/scan` | 传入路径列表，返回新增任务与扫描统计 |
| `GET` | `/api/config` | 读取当前配置（含输出目录相关字段） |
| `PUT` | `/api/config` | 保存配置到 `local_config.yaml` |
| `POST` | `/api/convert` | 提交本批任务快照（task_id、路径、码率、输出策略） |
| `POST` | `/api/cancel` | 取消全部 |
| `POST` | `/api/cancel/{task_id}` | 取消单任务 |
| `GET` | `/api/ffmpeg-status` | FFmpeg 是否可用及说明文案 |
| `GET` | `/api/batch` | 当前批次/任务执行快照（供 WS 重连后对齐状态） |

Sidecar **仅监听本机回环地址**（`127.0.0.1`），端口由 Tauri 在启动 sidecar 时分配并通过环境变量传给 sidecar，再由 Tauri 把 base URL 注入前端，避免写死冲突端口。

#### WebSocket `/ws`

事件类型（对齐现有 `WorkerEvent` 语义）：

- `task_started`
- `task_progress`（phase、percent、message）
- `task_done`
- `task_error`
- `task_skipped`
- `batch_progress`（done_count / total_count）
- `batch_finished`

前端按 `task_id` **增量 patch** 对应行，不得因进度事件重建整个列表。

#### 转换数据流

```text
用户点「开始」
  → React 冻结本批快照 → POST /api/convert
  → Sidecar 运行 batch_convert（并行 N）
  → 进度经 /ws 推送 → React 更新单行
  → 可继续 scan（仅下一批执行）
  → batch_finished → 工具栏反馈与按钮状态恢复
```

### 4. UI / 动效

信息架构保持现有 **单一工作区队列**（不对标多面板仪表盘）。

**布局**

1. 顶栏：标题、设置、FFmpeg 状态  
2. 输出到：源目录 / 指定目录  
3. 工具栏：全选、清空、反馈文案、开始 / 取消全部  
4. 持续导入区：拖放 + 选文件/文件夹  
5. 任务列表：勾选、路径、码率、状态/进度、行内取消、失败展开  

视觉语义色可延续现有 `gui/theme.py` 令牌（surface / accent / status），在 Web CSS 变量中重声明。

**动效（克制，有目的）**

| 场景 | 行为 |
|------|------|
| 任务进出列表 | 高度/透明度过渡（如 Framer Motion `AnimatePresence`） |
| 状态变化 | 进度条宽度平滑过渡；完成/失败短颜色过渡 |
| 设置 | 模态对话框 enter/exit（对等现有设置窗），避免硬切 |

任务数量很大时再引入虚拟滚动；少量任务不必。

**明确不做**：全页粒子/光效；为动画拆大量路由页。

### 5. 错误处理

| 场景 | 行为 |
|------|------|
| Sidecar 未就绪或崩溃 | 启动时轮询 health；失败展示可重试错误页；运行中断线提示并重连 WS |
| 扫描部分失败 | 统计反馈（添加/重复/无法解析），不清空已有队列 |
| 单任务失败 | `task_error` + 可展开详情与复制；同批其他任务继续 |
| 取消 | 全部/单任务；UI 显示「正在取消…」；结束后按现有成功/失败/取消汇总 |
| FFmpeg 缺失 | 顶栏警告；必要时禁用「开始」 |
| 配置写入失败 | 设置区内联错误，不伪装成功 |

### 6. 打包与开发工作流

**开发**

1. 启动 Python sidecar（热重载可选）  
2. `tauri dev`（含 Vite）  
3. Tauri 将 sidecar URL 注入前端  

**发行（Windows）**

- Tauri 构建主程序  
- Python sidecar 用 PyInstaller（或与现有 `build.spec` 同类方案）打成外部 sidecar 可执行文件，由 Tauri sidecar 配置拉起  
- 继续打包 `imageio-ffmpeg` 提供的 FFmpeg，用户无需自备  
- `local_config.yaml` 仍放在应用可写目录/旁路（与现行为一致：exe 旁覆盖配置）  

README 与 `build.bat`（或替代脚本）改为 Tauri + sidecar 构建说明；CustomTkinter 依赖与 GUI 入口从主路径移除。

### 7. 测试

- **保留**：`core/`、batch、cancel、进度映射等现有 pytest，作为业务真相源  
- **新增**：sidecar API 契约测试（scan/convert/cancel/config 与事件 JSON 形状）  
- **前端**：队列状态机单测（增量更新、批次冻结、按钮可用性）  
- **手工验收**：拖放导入、并行进度、单任务/全部取消、设置持久化、无系统 Python 的打包运行  

### 8. 迁移收尾

- 删除或停止维护 `gui_app.py` 与 `gui/` 作为产品入口（实现计划中一次性移除，避免双 GUI）  
- 从 `requirements.txt` 移除仅 GUI 使用的 CustomTkinter / tkinterdnd2（若 sidecar 不需要）  
- 文档更新为新桌面启动与构建方式  

## 成功标准

- 现有 GUI 能力对等：导入、队列、并行转换、进度、取消、设置、错误详情  
- 转换进行中界面可滚动、可继续导入，进度更新无明显整表闪烁/卡顿  
- 任务进出与设置开合有基础过渡动画  
- 打包产物在干净 Windows 机器上可完成一次转换（含 FFmpeg）  
- CLI 行为回归测试通过  

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Sidecar 端口占用 / 启动竞态 | 动态端口 + health 门闩后再显示主 UI |
| PyInstaller sidecar 体积偏大 | 接受工具型体积；排除无关依赖；与现 exe 体量同级预期 |
| WS 断线丢事件 | 重连后立即 `GET /api/batch` 拉取快照并覆盖本地执行态，再继续收事件 |
| 拖放路径与浏览器安全限制 | 文件路径一律经 Tauri 原生 API / 拖放事件拿到后再交给 scan |

## 实现顺序（概要）

1. Sidecar 骨架 + health/config + 复用 scan/convert/cancel  
2. React 单页队列 UI（无动画也可先通）+ REST/WS 联调  
3. Tauri 壳接入 sidecar 生命周期与原生对话框/拖放  
4. 动效与体验打磨  
5. 打包脚本、移除旧 GUI、文档与验收  

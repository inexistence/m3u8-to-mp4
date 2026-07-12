# 批量转换并行执行（方案 1）

日期：2026-07-12  
状态：待审阅

## 背景

GUI 的 `ConversionWorker._run` 与 CLI 目录模式（`main.py`）均按任务串行执行。批量多个 m3u8 时总耗时近似为各任务之和。现有取消链路（每任务 `cancel_event` → parser / FFmpeg）已就绪，适合在 Worker 层引入有限并发。

## 目标

- GUI 与 CLI 均支持并行转换同一批任务
- 并发数为**固定配置值**（默认 `2`），可在设置中修改
- 全局取消：中断所有正在跑的任务，未开跑标 `SKIPPED`（与现有语义一致）
- 每个任务有独立取消：
  - **RUNNING**：中断该任务（`ERROR` + 取消文案），同批其他任务继续
  - **PENDING（排队中）**：标 `SKIPPED`，不进入执行，同批其他继续
- 并行时输出文件名不撞车
- 任务行可同时显示多个 `RUNNING` 进度（沿用现有 `task_index` 事件）

## 非目标

- 不按 CPU 核数自动计算并发
- 不使用多进程
- 不新增 `CANCELLED` 任务状态（单任务取消仍用 `ERROR` + 取消文案；排队取消用 `SKIPPED`）
- 不改变单任务内部合片/封装逻辑（继续复用现有 `cancel_event`）
- 不在本批运行中途把新导入任务并入当前批（保持「下一批」行为）

## 设计

### 1. 配置

`GlobalConfig` 新增：

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `max_parallel_conversions` | `int` | `2` | 同时转换的最大任务数 |

约束：加载与保存时规范为整数，且 `>= 1`；非法或缺失回退默认 `2`。建议设置 UI 给出合理上限（例如 `1`–`8`），避免用户填过大拖垮磁盘/内存。

- `config.yaml` 可带默认值
- `local_config.yaml` / 设置对话框可覆盖
- `to_local_dict` / `apply_local_dict` / `reload_from_disk` 同步该字段

实际并发：

```text
workers = max(1, max_parallel_conversions)
```

不再与 `os.cpu_count()` 取 min。

### 2. 共享批处理模块

新增例如 `core/batch_convert.py`（名称可微调），职责：

- 输入：任务序列、`GlobalConfig`、可选进度/事件回调、取消控制器
- 按 `workers` 用 `concurrent.futures.ThreadPoolExecutor` 调度
- 每个任务调用 `M3U8Converter(...).convert(..., cancel_event=该任务的 Event)`
- GUI 与 CLI 共用，避免两套并行逻辑

`ConversionWorker` 变为薄封装：持有批处理、把内部回调映射为现有 `WorkerEvent`（`started` / `task_started` / `task_progress` / `task_done` / `task_error` / `finished` / `log`）。

CLI `main.py` 目录模式：发现多个入口后调用同一批处理（不依赖 GUI 事件，仅 print 进度/结果）。

### 3. 取消模型

```text
BatchCancelController
  batch_cancel: Event          # 全局取消
  task_cancels: list[Event]    # 与任务一一对应
```

| 操作 | 行为 |
|------|------|
| 全局取消 | `batch_cancel.set()`；对每个任务 `task_cancels[i].set()`；尚未领取的任务标 `SKIPPED`；已在跑的经现有链路抛 `ConversionCancelled` → `ERROR` |
| 单任务取消（RUNNING） | 仅 `task_cancels[i].set()` → 该任务 `ERROR`（取消文案）；池中其他任务不受影响 |
| 单任务取消（PENDING） | `task_cancels[i].set()`（或等价标记）；调度时发现已取消则标 `SKIPPED`，不调用 `convert` |

调度循环在提交/领取任务前检查该任务 Event（及可选的 batch Event）。`done_count` 仅统计成功完成（`DONE`），与现有一致。

线程安全：任务状态与事件回调用锁保护，或仅在持锁下改 `task.status`；向 GUI 的 `on_event` 仍通过 `after(0, ...)` 切回主线程。

### 4. GUI

**设置**

- 「转换设置」增加「同时转换数」控件（数字输入或下拉 `1`–`8`）
- 转换进行中仍不可打开设置（现有行为）

**任务行**

- 本批内状态为 `PENDING` 或 `RUNNING` 时显示行内「取消」
- 点击 → `worker.cancel_task(batch_index)`（或等价 API）
- `DONE` / `ERROR` / `SKIPPED` 不显示或不启用行内取消
- 工具栏全局「取消」保留；文案「正在取消…」仅用于全局取消

**进度**

- 允许多行同时 `RUNNING` + `set_task_progress`
- 队列反馈文案可继续用「已完成数 / 总数」；不必强制显示「当前并行数」

### 5. 输出路径竞态

`resolve_unique_output_path`（及必要时目录解析）使用**进程内锁**，保证「检查不存在 → 选用路径」原子性，避免并行任务落到同一输出文件名。

不引入跨进程文件锁（本应用单实例内并发即可）。

### 6. 错误与完成

- 单任务失败不影响池中其他任务（与串行时「失败后继续下一个」一致，只是重叠执行）
- 批结束仍发 `finished`；GUI `_finish_conversion` 汇总成功 / 失败 / 跳过
- 全局取消时 `was_cancelled` 逻辑保持；仅单任务取消不视为整批「用户取消」

### 7. 测试要点

- 并发数：`max_parallel_conversions=2` 时，峰值同时 `convert` 调用数 ≤ 2
- 全局取消：多个 RUNNING 均被中断；剩余 PENDING → `SKIPPED`
- 单任务取消 RUNNING：仅该任务 `ERROR`；其他可完成
- 单任务取消 PENDING：该任务 `SKIPPED`；不调用其 `convert`
- 输出路径：两任务同目录同 base_name 并行时得到不同路径
- CLI：目录下多文件时使用配置的并发数（可用 mock 断言）
- 回归：现有取消相关单测仍通过；串行等价于 `max_parallel_conversions=1`

## 实现顺序建议

1. 配置字段 + 设置 UI + 输出路径锁  
2. `core/batch_convert.py` + Worker 接入 + 单测  
3. 全局取消适配并行 + 单任务取消 API  
4. GUI 行内取消按钮  
5. CLI 接入  
6. 回归全量相关单测  

## 验收标准

1. 默认并发为 2；设置改为 1 时行为与当前串行一致  
2. GUI 批量可见多个任务同时「转换中」  
3. 全局取消能尽快停下所有进行中的任务，排队任务跳过  
4. 行内取消可中断单个 RUNNING 或跳过单个 PENDING，不影响其余  
5. CLI 扫目录转换同样并行，并遵守同一配置项  
6. 并行写出同一输出目录时不互相覆盖  

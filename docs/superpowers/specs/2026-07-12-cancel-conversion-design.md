# 转换取消可中断合片与 FFmpeg（方案 1）

日期：2026-07-12  
状态：待审阅

## 背景

当前「取消」只设置 `ConversionWorker._cancel`（`threading.Event`），仅在任务间隙检查。正在合片或 FFmpeg 封装的任务会跑完，长视频封装时用户会感觉取消无效。

## 目标

- 取消后，**当前任务**在合片循环与 FFmpeg 封装阶段均可尽快停止
- **被中断的当前任务**记为 `TaskStatus.ERROR`，`error_message` 为明确取消原因（例如「用户取消」），以便与失败任务一样展开详情、复制信息（用户取消有时也意味着发现问题）
- **尚未开始的后续任务**仍记为 `TaskStatus.SKIPPED`
- CLI（不传取消信号）行为不变
- 清理临时目录；删除取消导致的不完整输出 MP4

## 非目标

- 不新增 `CANCELLED` 任务状态
- 不中断单个 `.ts` 文件读盘/解密的微秒级中途（仅在分片边界检查）
- 不把「未开始就被跳过」的后续任务标成 ERROR（避免虚假失败噪音）

## 设计

### 1. 取消异常

在 `core` 新增轻量异常，例如 `core/utils/cancellation.py`：

```python
class ConversionCancelled(Exception):
    """用户请求取消转换。"""
```

用于合片与封装路径向上冒泡。Worker 将**当前被中断任务**标为 `ERROR`（带取消文案），以便走现有失败详情 UI；**不要**把取消与真正的技术失败混用同一套无文案的空消息。

### 2. 传递 `cancel_event`

类型：`threading.Event | None`（默认 `None` = 不可取消）。

调用链：

```
ConversionWorker._cancel
  → M3U8Converter.convert(..., cancel_event=...)
    → SimpleM3U8TsParser(..., cancel_event=...)
    → FfmpegMerger(..., cancel_event=...)
```

可选：converter / parser / merger 提供 `_raise_if_cancelled()`，在 `cancel_event is not None and cancel_event.is_set()` 时抛出 `ConversionCancelled`。

### 3. 合片阶段（分片边界）

在 `SimpleM3U8TsParser` 处理每个 `.ts` 分片**之前**（进入 `__decrypt_and_merge_ts` 有效路径或 `append` 前）调用 `_raise_if_cancelled()`。

取消时：

- 不再继续读后续行/分片
- `merge()` 的 `finally` 仍调用 `ts_merger.finish()` **或** 改为可中止的清理路径（见下）

**清理约定（推荐）：**

- 若已取消：跳过 FFmpeg 封装，只关闭并删除临时 `merged.ts` 目录
- 为此可在 `FfmpegMerger` 增加 `abort()` / `finish(cancelled=False)`，或在 `finish()` 开头检查 `cancel_event` 并走「仅清理、不封装」分支后抛出 `ConversionCancelled`

推荐实现：`finish()` 开头若已取消 → 关闭文件、`rmtree` 临时目录 → 抛 `ConversionCancelled`（不启动 FFmpeg）。`merge()` 的 `finally` 始终调用 `finish()`：若循环内已因取消抛出，`finish()` 只做幂等清理并再次抛出（或清理后让 `finally` 中的异常成为最终冒泡）；不得在取消后仍启动 FFmpeg。

### 4. FFmpeg 封装阶段

`FfmpegMerger._run_ffmpeg`：

1. `Popen(...)` 后保存 `self._process`
2. 读 `-progress` 每一行（或每读到进度）时检查 `cancel_event`
3. 若取消：`terminate()`；短超时后仍存活则 `kill()`；`wait()`；抛 `ConversionCancelled`
4. `finally`：`self._process = None`；临时目录仍由外层 `finish` 的 `finally` 清理
5. 若 `target_file_path` 已存在且本次为取消路径，删除不完整 MP4（`unlink(missing_ok=True)`）

`stdin=DEVNULL`、`-y` 保持不变。

### 5. Worker 行为

```text
cancel() → _cancel.set()
```

`_convert_one` / `_run`：

- 捕获 `ConversionCancelled`：当前任务 `status = ERROR`，`error_message = '用户取消'`（或异常消息）；发 `task_error` 以便刷新行并显示错误详情面板；**不**增加 `done_count`
- 循环中后续 `PENDING` 任务继续标 `SKIPPED`（现有逻辑保留）
- 若取消发生在任务开始前，行为与今日相同（仅 SKIPPED，无 ERROR）

注意：可用专用 `except ConversionCancelled` 设置上述 ERROR 文案后再交给 `_run` 发 `task_error`；文案必须稳定可读，便于用户复制排查「为何中途停」。

### 6. GUI

`cancel_conversion` 仍只调用 `worker.cancel()`；按钮「正在取消…」逻辑不变。  
被中断任务走现有 `ERROR` 详情（摘要 + 复制）；批次汇总里该任务计入「失败」，`was_cancelled` 对话框仍可提示用户主动取消过。无需为取消单独改详情面板。

### 7. 测试

最少覆盖：

1. 合片循环：mock 分片处理，`cancel_event.set()` 后抛 `ConversionCancelled`，且未调用 FFmpeg
2. `_run_ffmpeg`：mock `Popen`，取消后调用 `terminate`（或 `kill`），抛 `ConversionCancelled`
3. Worker：取消当前任务 → `ERROR` 且 `error_message` 含取消说明；后续未开跑任务 → `SKIPPED`

## 风险与边界

| 风险 | 处理 |
|------|------|
| `terminate` 后 Windows 上僵尸/句柄 | `wait()`；超时 `kill()` |
| `finish()` 与循环双重抛取消 | 取消路径幂等：已清理则直接再抛或 no-op 后抛 |
| 取消与正常结束竞态 | 正常 `returncode==0` 且未取消 → 成功；已 set 则优先取消语义 |
| 不完整 MP4 | 取消路径删除 `target_file_path` |

## 验收标准

1. 合片中点取消：当前任务变为失败（可看「用户取消」详情），临时目录被删，无新 MP4（或半成品被删）
2. FFmpeg 封装中点取消：子进程被结束，当前任务失败详情可见，半成品 MP4 被删
3. 同批后续未开始任务为「已跳过」，不出现假失败详情
4. 未点取消：转换结果与现网一致
5. CLI 不传 event：行为不变

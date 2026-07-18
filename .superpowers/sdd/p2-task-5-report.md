# Phase 2 Task 5 Report

## Status

DONE

## Commit

`77d755d feat: complete browser queue convert cancel flow`

## Changes

- 启动批次时提交选中任务的 sidecar ID、路径、码流索引和主播放列表标记。
- 接入全部取消与单任务取消 API，并为对应按钮增加「正在取消…」本地状态和失败反馈。
- 根据任务终态生成「成功 / 失败 / 取消」批次汇总。
- WebSocket 关闭 1 秒后重连，并通过 `GET /api/batch` 将快照合并到队列任务。
- 增加 UI 开发说明以及启动、取消、批次汇总和断线恢复回归测试。

## Verification

- `cd ui && npm test`：2 个测试文件、12 个测试全部通过。
- `cd ui && npm run build`：通过。
- `python -m unittest tests.test_sidecar_api tests.test_sidecar_ws -v`：6 个测试全部通过。
- `git diff --check -- ui`：通过。

## Review Fix

- 为初始与重连批次快照增加请求代次保护；若请求期间收到 `batch_finished`，则忽略该过期快照，避免恢复错误的转换状态。
- 将浏览器批次反馈对齐 `core.queue_messages.batch_feedback`，失败批次追加「；点击失败任务可查看详情」。
- `cd ui && npm test`：2 个测试文件、13 个测试全部通过。

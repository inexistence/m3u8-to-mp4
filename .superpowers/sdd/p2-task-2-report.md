# Phase 2 Task 2 报告

## 实现

- 新增共享类型：队列任务、扫描响应、转换请求、配置、批次快照及 WebSocket 事件。
- 新增 sidecar API client，扫描条目包含 `task_id` 与 `is_master_playlist`；转换请求完整发送 `task_id`、`path`、`selected_stream_index`、`is_master_playlist`。
- 新增 WebSocket client，提供 `connect`、`disconnect`、`onEvent`。
- 新增队列 reducer 及全部指定 action；`ADD_ENTRIES` 按路径去重，并优先使用 sidecar 的 `task_id`，仅缺失时调用 `crypto.randomUUID()`。
- `CLEAR` 在转换期间保持 no-op。

## TDD 证据

### RED

先创建 `ui/src/state/queueStore.test.ts`，再运行 `npm test`。

- 退出码：1
- 结果：1 个 suite 失败，无法解析尚不存在的 `./queueStore`
- 失败原因符合预期：生产模块尚未实现

### GREEN

实现后运行 `npm test`：

- 退出码：0
- Test Files：1 passed
- Tests：4 passed
- 覆盖：按路径去重并保留稳定 ID、扫描 `task_id` 映射、单任务 patch 保持其他对象引用、`START_BATCH` 冻结选中 ID

## 验证

- `npm test`：4/4 通过
- `npm run build`：退出码 0
- `npm run lint`：退出码 0

## 注意事项

- npm 输出已有的 `Unknown env config "devdir"` 警告；不影响测试、构建或 lint。

## 修复：WebSocket close race

**问题**：旧 socket 在较新的 `connect()` 之后触发 `onclose` 时，会无条件将 `this.socket` 置为 `null`，误清除仍活跃的新连接。

**修复**：`onclose` 仅在 `event.target === this.socket` 时清空引用；`connect()` 将 socket 存为局部变量再赋给 `this.socket`，避免 stale handler 影响新实例。

### 测试

```
npm test
```

- 退出码：0
- Test Files：1 passed
- Tests：4 passed

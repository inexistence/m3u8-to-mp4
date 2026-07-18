# Phase 3 Task 1 实施报告

## 状态

已完成 Tauri 2 工程初始化、React UI 接入、桌面端冒烟验证及进程清理。

提交：`e39dd7c chore: initialize Tauri 2 shell for React UI`

## 变更

- 在仓库根目录生成 `src-tauri/`，应用标识为 `com.m3u8tomp4.app`。
- 配置 `frontendDist` 为 `../ui/dist`，开发地址为 `http://127.0.0.1:5173`。
- Tauri 会从 `ui/` 执行前端钩子，因此配置为 `npm run dev` / `npm run build`；使用 `npm --prefix ui ...` 会错误解析为 `ui/ui/package.json`。
- 窗口标题设为 `m3u8 → mp4`，默认尺寸 `900x700`，最小尺寸 `760x560`。
- 在 `ui/` 安装：
  - `@tauri-apps/cli`（devDependency）
  - `@tauri-apps/api`
  - `@tauri-apps/plugin-dialog`
  - `@tauri-apps/plugin-shell`
  - `@tauri-apps/plugin-fs`
- Vite 固定监听 `127.0.0.1:5173`，并启用 `strictPort`，防止 Tauri 连接到错误端口。

## 验证

- `npm --prefix ui run build`：通过，Vite 8.1.5 完成 430 个模块构建。
- `cargo check --manifest-path src-tauri\Cargo.toml`：通过，dev profile 检查完成。
- `cargo build --manifest-path src-tauri\Cargo.toml --verbose`：通过，生成桌面可执行程序。
- `.\ui\node_modules\.bin\tauri.cmd dev`：通过。
  - Vite 在 `http://127.0.0.1:5173/` 启动。
  - Rust dev profile 编译完成。
  - `app.exe` 成功启动，进程计数为 1。
  - React 页面 HTTP 探测返回 200。
- 冒烟结束后已终止 Tauri/Vite 进程；端口 5173 监听数为 0，项目相关残留进程数为 0。

## 说明

- 第一次 `tauri dev` 暴露了前端钩子执行目录问题，已根据实际错误路径修正并重新验证。
- 一次首次完整链接在后台日志停留于 358/360 且进程消失；随后独立 `cargo build` 成功，最终 `tauri dev` 在 10.29 秒内完成增量编译并启动窗口。
- 本任务仅安装前端插件包，尚未在 Rust 端注册 dialog/shell/fs 插件；按任务范围留待后续接线。

## 审查修复

- 提交 `ui/package-lock.json` 与 `src-tauri/Cargo.lock`，确保 npm 与 Rust 构建可复现。
- 新增根目录 npm 入口，并在 `ui/package.json` 暴露 `tauri` 脚本。
- 从仓库根目录运行 `npm run dev` 即可启动 Tauri 开发模式；`npm run build` 可执行桌面应用构建。

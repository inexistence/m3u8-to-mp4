# m3u8-to-mp4

将本地 m3u8 索引及其 ts 分片合并为 MP4 文件的 Windows 桌面应用与命令行工具。支持 AES-128 解密、多码率索引解析，以及 `#EXT-X-DISCONTINUITY` 分段处理。

## 功能特性

- 合并本地 `.m3u8` 索引引用的 ts 分片，输出 MP4
- 支持 `AES-128` 加密分片解密（需本地存在 key 文件）
- 自动解析主播放列表（`#EXT-X-STREAM-INF`），支持按带宽自动选流或交互式选择
- 支持单文件或递归扫描目录下所有 `.m3u8` 文件
- 提供 Windows 桌面应用（Tauri + React）：批量队列、并行转换（默认 2 路）、输出目录选择及任务进度/失败详情
- 通过 `config.yaml` 配置输出文件名、输出目录、分段跳过等行为

## 环境要求

- Python 3.10+（CLI 与 sidecar）
- Node.js 18+ 与 Rust（开发/打包桌面应用）
- [FFmpeg](https://ffmpeg.org/download.html)：通过 `imageio-ffmpeg` 自动提供（源码运行与发行版均适用）；也可自行安装并加入系统 `PATH`
- 发行版会打包 sidecar 与 `imageio-ffmpeg` 自带的 FFmpeg，无需用户额外下载

## 安装

```shell
# 创建虚拟环境
python -m venv .venv
```

### Windows PowerShell

```shell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1
```

若提示执行策略限制，可先运行：

```shell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

```shell
# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端与 Tauri 依赖
npm install
npm --prefix ui install
```

## 使用方法

### 桌面应用（Windows）

开发模式（热重载 UI，由 Tauri 拉起 Python sidecar）：

```shell
.\scripts\dev.ps1
```

或：

```shell
npm run tauri dev
```

发行打包：

```shell
.\scripts\build.ps1
```

或：

```shell
.\build.bat
```

打包会先用 PyInstaller 构建 `m3u8-sidecar`，再由 Tauri 打出安装包/可执行文件。构建通过 `imageio-ffmpeg` 收集并打入平台 FFmpeg。如需覆盖默认配置，可在应用数据目录或约定位置放置 `local_config.yaml`。

#### 桌面应用使用

1. 导入 `.m3u8` 文件或文件夹；程序会扫描入口索引并加入转换队列。
2. 选择输出到「源目录」或「指定目录」。源目录模式下，每个任务输出到各自 m3u8 所在目录。
3. 勾选要转换的任务；主播放列表可选择码率。
4. 开始转换后，按设置中的并发数（默认 2，可选 1–8）并行执行。
5. 任务显示合片与 FFmpeg 封装阶段进度；失败任务可查看错误详情。
6. 转换进行中可取消全部，或取消单个排队/运行中的任务。

在设置中可调整同时转换数、输出文件名、AES-128 分片 IV 模式及分段处理选项。设置会保存到 `local_config.yaml`，并在下一次转换时生效。

### 开发 / 发行 / 验收

| 场景 | 命令 |
|------|------|
| 本地开发（Tauri + Python sidecar） | `.\scripts\dev.ps1` 或 `npm run dev` |
| 发行打包（sidecar → externalBin → 安装包） | `.\scripts\build.ps1` 或 `.\build.bat` |
| Python 单测 | `python -m unittest discover -s tests -v` |
| 前端单测 | `npm --prefix ui test` |
| CLI | `python .\main.py "path\to\index.m3u8"` |

`scripts\dev.ps1` / `scripts\build.ps1` 会将 `%USERPROFILE%\.cargo\bin` 加入 `PATH`，便于找到 `cargo` / `rustc`。

发行验收要点（打包产物或 `tauri dev` 手工确认）：

1. 无系统 Python 时，双击/运行 Tauri 主程序仍能出窗口（sidecar 由壳拉起）
2. Sidecar 自动启动，健康检查通过（界面显示「Sidecar 已连接」）
3. 拖放 `.m3u8` / 选文件夹导入
4. 设置并行数并持久化到 `local_config.yaml`
5. 开始转换后进度平滑更新，无整表闪烁
6. 行内取消与取消全部可用
7. 失败任务可展开并复制错误信息
8. FFmpeg 不可用时顶栏有明确提示（「FFmpeg 不可用」+ 详情）
9. 开发环境 `python main.py` CLI 仍可用

### 命令行

将 `index.m3u8` 文件路径，或包含该文件的文件夹路径作为参数传入。默认输出 MP4 到对应 `index.m3u8` 所在目录；配置 `output_directory` 后则输出到指定目录。

```shell
python .\main.py "path\to\index.m3u8"
```

```shell
# 递归扫描目录及所有子目录中的 .m3u8 文件并逐一转换
python .\main.py "path\to\directory"
```

传入目录时，会递归找出该目录树下全部的 `.m3u8` 文件，并自动跳过被主播放列表引用的子码率索引（如 `720p/index.m3u8`），避免重复转换。按路径排序后并行处理入口文件，并发数由 `max_parallel_conversions` 控制（默认 2，可选 1–8）。

### 输入要求

- m3u8 索引文件与 ts 分片、key 文件需位于同一目录（或索引中引用的相对路径可正确解析）
- 加密流需在索引中声明 `#EXT-X-KEY`，且 key 文件已下载到本地

## 配置

项目根目录下的 `config.yaml` 控制转换行为：

```yaml
# 是否跳过 m3u8 的第一段内容（part 0）
# 仅在索引文件包含 #EXT-X-DISCONTINUITY 标签时生效
skip_first_part: false

# 输出 MP4 文件名
# 可使用 __DIR_NAME__ 表示使用 index.m3u8 所在文件夹名作为文件名
output_file_name: __DIR_NAME__

# 输出目录。留空或设为 null 时，输出到各 m3u8 所在目录
# 可填写绝对路径，例如 C:\Users\name\Videos
output_directory: null

# 遇到 #EXT-X-DISCONTINUITY 切换分段时，是否重置解密器
reset_decryption_if_part_changed: true

# AES-128 分片 IV 获取方式
# - auto: 自动检测（默认）
# - prepended: 分片前 16 字节密文作为 IV（常见于迅雷等下载器）
# - hls: 标准 HLS，整段密文 + m3u8 声明 IV 或分片序号
aes_iv_mode: auto

# 主播放列表（多码率）流选择策略，仅命令行使用
# 桌面应用中请在每个任务行选择码率
# - highest_bandwidth: 选带宽最高的（默认）
# - lowest_bandwidth: 选带宽最低的
# - first: 选第一个
# - interactive: 扫描所有流并让用户交互选择
# - resolution:1280x720: 匹配指定分辨率
# - index:0: 按序号选择（从 0 开始）
stream_selection: highest_bandwidth

# 同时转换的最大任务数（桌面应用 / CLI 批量）
# 取值 1–8；默认 2
max_parallel_conversions: 2
```

如需本地覆盖配置且不希望提交到版本库，可在项目根目录创建 `local_config.yaml`，字段与 `config.yaml` 相同，同名项优先生效。指定的输出目录必须已存在；输出文件重名时程序会自动追加 m3u8 名称或序号以避免覆盖。

## 项目结构

```
m3u8-to-mp4/
├── main.py                 # 命令行入口
├── build.bat               # Windows 一键发行打包（调用 scripts/build.ps1）
├── config.yaml             # 默认配置
├── core/                   # 转换核心与批处理
├── sidecar/                # FastAPI sidecar（桌面应用后端）
├── ui/                     # React 前端
├── src-tauri/              # Tauri 壳
├── scripts/                # 开发与打包脚本
└── requirements.txt
```

## 依赖说明

| 库 | 用途 |
|---|---|
| fastapi / uvicorn | Python sidecar HTTP / WebSocket |
| ffmpeg-python | 调用 FFmpeg 合并 ts 分片 |
| imageio-ffmpeg | 解析并提供 FFmpeg 可执行文件（含打包进发行版的平台二进制） |
| pycryptodome | AES-128 分片解密 |
| PyYAML | 读取配置文件 |
| tqdm / colorama 等 | 辅助工具库 |

桌面 UI 依赖见 `ui/package.json`；壳层见 `src-tauri/`。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

发行版会通过 `imageio-ffmpeg` 内置 FFmpeg 可执行文件。当前 Windows 构建按 **GPL v3+** 分发；本项目以独立子进程调用，不与其链接。第三方组件的来源与许可详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

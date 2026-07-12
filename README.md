# m3u8-to-mp4

将本地 m3u8 索引及其 ts 分片合并为 MP4 文件的 Windows 桌面应用与命令行工具。支持 AES-128 解密、多码率索引解析，以及 `#EXT-X-DISCONTINUITY` 分段处理。

## 功能特性

- 合并本地 `.m3u8` 索引引用的 ts 分片，输出 MP4
- 支持 `AES-128` 加密分片解密（需本地存在 key 文件）
- 自动解析主播放列表（`#EXT-X-STREAM-INF`），支持按带宽自动选流或交互式选择
- 支持单文件或递归扫描目录下所有 `.m3u8` 文件
- 提供 Windows GUI：拖放导入、批量队列、输出目录选择及任务行内进度/失败详情
- 通过 `config.yaml` 配置输出文件名、输出目录、分段跳过等行为

## 环境要求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html)：通过 `imageio-ffmpeg` 自动提供（源码运行与发行版 exe 均适用）；也可自行安装并加入系统 `PATH`
- 发行版 `m3u8-to-mp4.exe` 会打包 `imageio-ffmpeg` 及其自带 FFmpeg，无需用户额外下载

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
# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 桌面应用（Windows）

安装依赖后，可直接启动 GUI：

```shell
python gui_app.py
```

或打包为独立 exe（双击运行，无需 Python 环境）：

```shell
.\build.bat
```

打包完成后，可执行文件位于 `dist\m3u8-to-mp4.exe`。构建会通过 `imageio-ffmpeg` 收集并打入平台 FFmpeg，最终用户无需自行下载。将 exe 放到任意目录即可使用；如需覆盖默认配置，可在 exe 同目录放置 `local_config.yaml`。

#### GUI 使用

主窗口以单个转换队列为核心：输出目录栏、批量操作栏、持续导入入口和任务列表始终处于同一工作区。

1. 在持续导入栏拖放 `.m3u8` 文件/文件夹，或选择文件、文件夹。程序会扫描入口索引、跳过重复项，并在工具栏内显示导入结果。
2. 在“输出到”栏选择“源目录”或“指定目录”。切换至指定目录时选择目标文件夹；目录名称可点击打开。源目录模式下，每个任务输出到各自 m3u8 所在目录。
3. 勾选要转换的任务。主播放列表会显示可选码率下拉框；单流任务显示“码率：单流”。
4. 点击“开始转换”。已选任务会冻结为当前批次，运行时可继续导入任务，但新增任务仅在下一批执行。
5. 任务行显示当前阶段的真实进度：合片阶段与 FFmpeg 封装阶段依次进行。失败任务可展开查看和复制错误详情。

点击右上角“设置”可调整输出文件名、AES-128 分片 IV 模式及分段处理选项。设置会保存到 `local_config.yaml`，并在下一次转换时生效；转换进行中无法打开设置。输出目录在队列顶部设置，同样会写入 `local_config.yaml`。

### 命令行

将 `index.m3u8` 文件路径，或包含该文件的文件夹路径作为参数传入。默认输出 MP4 到对应 `index.m3u8` 所在目录；配置 `output_directory` 后则输出到指定目录。

```shell
python .\main.py "path\to\index.m3u8"
```

```shell
# 递归扫描目录及所有子目录中的 .m3u8 文件并逐一转换
python .\main.py "path\to\directory"
```

传入目录时，会递归找出该目录树下全部的 `.m3u8` 文件，并自动跳过被主播放列表引用的子码率索引（如 `720p/index.m3u8`），避免重复转换。按路径排序后依次处理入口文件。

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
# GUI 中请在每个任务行选择码率
# - highest_bandwidth: 选带宽最高的（默认）
# - lowest_bandwidth: 选带宽最低的
# - first: 选第一个
# - interactive: 扫描所有流并让用户交互选择
# - resolution:1280x720: 匹配指定分辨率
# - index:0: 按序号选择（从 0 开始）
stream_selection: highest_bandwidth
```

如需本地覆盖配置且不希望提交到版本库，可在项目根目录创建 `local_config.yaml`，字段与 `config.yaml` 相同，同名项优先生效。指定的输出目录必须已存在；输出文件重名时程序会自动追加 m3u8 名称或序号以避免覆盖。

## 项目结构

```
m3u8-to-mp4/
├── main.py                 # 命令行入口
├── gui_app.py              # 桌面应用入口
├── build.bat               # Windows 一键打包脚本
├── build.spec              # PyInstaller 配置
├── config.yaml             # 默认配置
├── core/
│   ├── discovery.py        # m3u8 扫描与码率信息
│   ├── m3u8converter.py    # 转换流程编排
│   ├── m3u8_stream.py      # 主播放列表解析、流选择与过滤
│   ├── m3u8_ts_parser.py   # 媒体播放列表解析、分片解密与合并
│   ├── decrypt/            # ts 分片解密（AES-128）
│   ├── merge/              # ts 合并（流式写入 + FFmpeg 封装）
│   └── utils/              # 配置、文件读写等工具
├── gui/                    # 桌面应用界面
└── requirements.txt
```

## 依赖说明

| 库 | 用途 |
|---|---|
| customtkinter | 桌面应用界面 |
| tkinterdnd2 | 拖放文件/文件夹 |
| ffmpeg-python | 调用 FFmpeg 合并 ts 分片 |
| imageio-ffmpeg | 解析并提供 FFmpeg 可执行文件（含打包进发行版的平台二进制） |
| pycryptodome | AES-128 分片解密 |
| PyYAML | 读取配置文件 |
| tqdm / colorama 等 | 辅助工具库 |

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

发行版会通过 `imageio-ffmpeg` 内置 FFmpeg 可执行文件。当前 Windows 构建按 **GPL v3+** 分发；本项目以独立子进程调用，不与其链接。第三方组件的来源与许可详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

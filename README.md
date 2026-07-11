# m3u8-to-mp4

将本地 m3u8 索引及其 ts 分片合并为 MP4 文件的命令行工具。支持 AES-128 解密、多码率索引解析，以及 `#EXT-X-DISCONTINUITY` 分段处理。

## 功能特性

- 合并本地 `.m3u8` 索引引用的 ts 分片，输出 MP4
- 支持 `AES-128` 加密分片解密（需本地存在 key 文件）
- 自动解析主播放列表（`#EXT-X-STREAM-INF`），定位实际 ts 索引文件
- 支持单文件或递归扫描目录下所有 `.m3u8` 文件
- 通过 `config.yaml` 配置输出文件名、分段跳过等行为

## 环境要求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html)（需已安装并将 `bin` 目录加入系统 `PATH`）

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

将 `index.m3u8` 文件路径，或包含该文件的文件夹路径作为参数传入。输出 MP4 将生成在对应 `index.m3u8` 所在目录下。

```shell
python .\main.py "path\to\index.m3u8"
```

```shell
# 递归扫描目录及所有子目录中的 .m3u8 文件并逐一转换
python .\main.py "path\to\directory"
```

传入目录时，会递归找出该目录树下全部的 `.m3u8` 文件（包括当前目录与子目录中的多个文件），按路径排序后依次处理。

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

# 遇到 #EXT-X-DISCONTINUITY 切换分段时，是否重置解密器
reset_decryption_if_part_changed: true

# AES-128 分片 IV 获取方式
# - auto: 自动检测（默认）
# - prepended: 分片前 16 字节密文作为 IV（常见于迅雷等下载器）
# - hls: 标准 HLS，整段密文 + m3u8 声明 IV 或分片序号
aes_iv_mode: auto
```

如需本地覆盖配置且不希望提交到版本库，可在项目根目录创建 `local_config.yaml`，字段与 `config.yaml` 相同，同名项优先生效。

## 项目结构

```
m3u8-to-mp4/
├── main.py                 # 命令行入口
├── config.yaml             # 默认配置
├── core/
│   ├── m3u8converter.py    # m3u8 解析与转换流程
│   ├── decrypt/            # ts 分片解密（AES-128）
│   ├── merge/              # ts 合并（FFmpeg concat）
│   └── utils/              # 配置、文件读写等工具
└── requirements.txt
```

## 依赖说明

| 库 | 用途 |
|---|---|
| ffmpeg-python | 调用 FFmpeg 合并 ts 分片 |
| pycryptodome | AES-128 分片解密 |
| PyYAML | 读取配置文件 |
| tqdm / colorama 等 | 辅助工具库 |

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

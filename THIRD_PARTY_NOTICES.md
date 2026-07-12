# 第三方组件说明

本项目（m3u8-to-mp4）采用 [Apache License 2.0](LICENSE)。发行版与开发依赖中还包含以下第三方组件。

## imageio-ffmpeg

- 用途：解析 FFmpeg 路径；打包 Windows 发行版时通过 PyInstaller `collect_all('imageio_ffmpeg')` 将其自带的平台二进制打入 `m3u8-to-mp4.exe`。源码运行与发行版均通过 `imageio_ffmpeg.get_ffmpeg_exe()` 获取可执行文件（依次尝试环境变量、自带二进制、conda、系统 PATH）。
- 许可：[BSD-2-Clause](https://github.com/imageio/imageio-ffmpeg/blob/master/LICENSE)
- 项目主页：https://github.com/imageio/imageio-ffmpeg

## FFmpeg

- 用途：将合并后的 TS 流封装为 MP4。本项目通过独立子进程调用 FFmpeg，不与其静态或动态链接。
- 来源：由 `imageio-ffmpeg` 分发的平台二进制。当前 Windows 版本对应 `ffmpeg-win-x86_64-v7.1.exe`（`7.1-essentials_build`，构建方 www.gyan.dev）。
- 许可：该 Windows 构建启用了 `--enable-gpl` 与 `--enable-version3`，因此按 **GNU GPL v3 或更新版本** 分发。可用 `ffmpeg -L` 查看具体声明。
- 上游与许可说明：
  - https://ffmpeg.org/
  - https://ffmpeg.org/legal.html
  - https://www.gnu.org/licenses/gpl-3.0.html

其他平台（macOS / Linux）上 `imageio-ffmpeg` 自带的 FFmpeg 构建配置可能不同；请以该平台二进制上 `ffmpeg -L` / `ffmpeg -version` 的输出为准。

重新分发包含 FFmpeg 的发行版时，请遵守其所适用的 GPL（或 LGPL）条款，包括按要求提供或指向对应源代码的获取方式。

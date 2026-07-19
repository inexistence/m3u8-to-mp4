# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.0.0] - 2026-07-19

- 首次正式发布：Windows GUI 与命令行，将本地 m3u8 / ts 合并为 MP4
- 支持 AES-128 分片解密、多码率主播放列表选流、`#EXT-X-DISCONTINUITY` 分段处理
- GUI：拖放导入、批量队列、并行转换、任务进度与取消
- 发行包经 GitHub Actions 构建，内置 FFmpeg（imageio-ffmpeg），提供 zip 与 SHA256 校验

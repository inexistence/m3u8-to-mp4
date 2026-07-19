---
name: publish-release
description: >-
  Publishes a GitHub Release for m3u8-to-mp4 by updating CHANGELOG.md, ensuring
  main is pushed, tagging v*, and verifying the Release workflow assets (zip +
  sha256). Use when the user asks to publish, release, cut a version, 发版,
  发布, 打 tag, 或创建 GitHub Release.
---

# 发布版本（GitHub Release）

本仓库通过推送 `v*` tag（或 Actions 手动 Run）触发 `.github/workflows/release.yml`，构建 Windows zip + SHA256 并创建 Release。

## 前置条件

- 工作目录为仓库根；默认在 **已推送到 origin 的 `main`** 上发版
- 本地改动已提交；发版相关提交已在 `origin/main`
- 已登录 `gh`（验证 Release 时需要）

若用户未给版本号，先问清：`vX.Y.Z` 或预发布（如 `v1.2.0-beta.1`）。

## 进度清单

复制并勾选：

```
发布进度:
- [ ] 1. 确认版本号与分支
- [ ] 2. 更新 CHANGELOG.md
- [ ] 3. 提交并推送 main（如有变更）
- [ ] 4. 打 annotated tag 并推送
- [ ] 5. 等待 Actions 成功
- [ ] 6. 核对 Release 资产与说明
```

## 步骤

### 1. 确认版本与分支

```powershell
git status -sb
git branch --show-current
git log -1 --oneline
```

- 版本规范为带 `v` 前缀（`v1.0.0`）。用户给 `1.0.0` 时先规范化为 `v1.0.0`。
- 含 `-alpha` / `-beta` / `-rc`（不区分大小写）→ GitHub 会标为 **Pre-release**。
- 不在脏工作区直接打 tag；先处理未提交改动。
- 若当前不在 `main`：合并/rebase 到 `main` 后再发，或征得用户同意在当前已推送分支发版。

### 2. 更新 CHANGELOG.md

编辑根目录 `CHANGELOG.md`：

1. 把 `[Unreleased]` 下要发布的条目移到新章节：
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   - 用户可见的变更说明（中文即可）
   ```
2. 保留空的 `## [Unreleased]` 在文件顶部附近。
3. 删除或改写占位段落（如 `TBD`、`placeholder`），不要把占位内容发进正式版。

Release 说明由 CI 调用 `scripts/release_notes.py` 生成：**优先**抽取该版本 CHANGELOG 章节；缺失则用上一 tag 到当前 tag 的 commit 列表；手动 Run 时可覆盖 `notes`。

本地预览（可选）：

```powershell
python scripts/release_notes.py --version vX.Y.Z --changelog CHANGELOG.md
python scripts/release_notes.py --version vX.Y.Z-beta.1 --check-prerelease
```

### 3. 提交并推送 main

仅当 CHANGELOG 或其它发版准备有改动时：

```powershell
git add CHANGELOG.md
git commit -m "docs: update changelog for vX.Y.Z"
git push origin main
```

确认 `main` 与 `origin/main` 一致后再打 tag。未获用户明确要求时不要 `git push --force`。

### 4. 打 tag 并推送（推荐主路径）

```powershell
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

**不要**用无分离 HEAD 的随意提交打正式版 tag，除非用户明确指定 commit。

备用：GitHub → Actions → **Release** → **Run workflow**，输入版本号（可带或不带 `v`）。优先推荐 tag 推送；手动路径在 tag 已存在时会 checkout 该 tag 再构建。

### 5. 等待并核对 Actions

```powershell
gh run list --workflow=release.yml --limit 5
gh run watch
```

失败则读日志修复后：删远端失败 tag（仅当用户同意且 Release 未产生有效资产时）、修代码/changelog、重打 tag。同一版本并发由 workflow `concurrency` 串行化。

### 6. 核对 Release

```powershell
gh release view vX.Y.Z
```

必须满足：

| 检查项 | 期望 |
|--------|------|
| 资产 | `m3u8-to-mp4-vX.Y.Z-windows-x64.zip` |
| 校验 | `m3u8-to-mp4-vX.Y.Z-windows-x64.zip.sha256` |
| 说明 | 含 CHANGELOG 该版本内容（或合理 commit 回退）+ footer（Windows exe / FFmpeg / THIRD_PARTY_NOTICES） |
| Pre-release | 预发布 tag 为 true；正式版为 false |

向用户返回：Release URL、两个资产名、是否 Pre-release。

## 禁止事项

- 不跳过 CHANGELOG 更新直接打正式版 tag（用户明确说「跳过 changelog / 仅用 commit 说明」除外）
- 不修改 `build.spec` 打包语义来「顺便」发版
- 不强制推送 tag/分支，除非用户明确要求
- 不把 `.env`、密钥、本地路径写进 Release notes

## 常见问题

| 情况 | 处理 |
|------|------|
| tag 已存在 | 与用户确认：复用并手动重跑 workflow，或改用新版本号 |
| Release 已存在、只需重传资产 | `gh workflow run release.yml -f version=vX.Y.Z`（notes 默认不会重写） |
| 只要草稿/预发布 | 使用 `-beta` / `-rc` 等后缀 tag |
| 本地想先验证打包 | `.\build.bat`，产物 `dist\m3u8-to-mp4.exe`（不替代 CI Release） |

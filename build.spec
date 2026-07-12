# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = [('config.yaml', '.'), ('gui/theme.json', 'gui')]
datas += collect_data_files('customtkinter')

dnd_datas, dnd_binaries, dnd_hiddenimports = collect_all('tkinterdnd2')
datas += dnd_datas
hiddenimports = list(dnd_hiddenimports)

ffmpeg_datas, ffmpeg_binaries, ffmpeg_hiddenimports = collect_all('imageio_ffmpeg')
datas += ffmpeg_datas
hiddenimports += list(ffmpeg_hiddenimports)

ffmpeg_executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
if not ffmpeg_executable.is_file():
    raise FileNotFoundError(f'无法找到用于打包的 FFmpeg：{ffmpeg_executable}')

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=dnd_binaries + ffmpeg_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='m3u8-to-mp4',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # FFmpeg 体积大，UPX 压缩收益有限，且易触发解压异常或杀软误报
    upx_exclude=[ffmpeg_executable.name],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

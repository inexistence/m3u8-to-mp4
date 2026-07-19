# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_all

block_cipher = None

spec_dir = Path(SPECPATH).resolve()
repo_root = spec_dir.parent

datas = [(str(repo_root / 'config.yaml'), '.')]
hiddenimports = [
    'sidecar',
    'sidecar.app',
    'sidecar.session',
    'sidecar.events',
    'sidecar.schemas',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
]

ffmpeg_datas, ffmpeg_binaries, ffmpeg_hiddenimports = collect_all('imageio_ffmpeg')
datas += ffmpeg_datas
hiddenimports += list(ffmpeg_hiddenimports)

fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all('fastapi')
datas += fastapi_datas
hiddenimports += list(fastapi_hiddenimports)

uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all('uvicorn')
datas += uvicorn_datas
hiddenimports += list(uvicorn_hiddenimports)

ffmpeg_executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
if not ffmpeg_executable.is_file():
    raise FileNotFoundError(f'FFmpeg not found for packaging: {ffmpeg_executable}')

a = Analysis(
    [str(spec_dir / '__main__.py')],
    pathex=[str(repo_root)],
    binaries=ffmpeg_binaries + fastapi_binaries + uvicorn_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['customtkinter', 'tkinterdnd2', 'tkinter'],
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
    name='m3u8-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[ffmpeg_executable.name],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

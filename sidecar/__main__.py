from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn

from sidecar.app import create_app


def _ensure_stdio() -> None:
    """Windowed PyInstaller builds leave stdout/stderr as None; restore sinks."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')


def main() -> None:
    if getattr(sys, 'frozen', False):
        os.chdir(Path(sys.executable).resolve().parent)
        _ensure_stdio()

    host = '127.0.0.1'
    port = int(os.environ.get('M3U8_SIDECAR_PORT', '8765'))
    # Server API is more reliable than uvicorn.run() under PyInstaller (esp. console=False).
    config = uvicorn.Config(create_app(), host=host, port=port, log_level='info')
    server = uvicorn.Server(config)
    server.run()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

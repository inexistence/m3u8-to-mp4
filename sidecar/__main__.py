from __future__ import annotations

import os

import uvicorn

from sidecar.app import create_app


def main() -> None:
    host = '127.0.0.1'
    port = int(os.environ.get('M3U8_SIDECAR_PORT', '8765'))
    uvicorn.run(create_app(), host=host, port=port, log_level='info')


if __name__ == '__main__':
    main()

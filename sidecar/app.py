from __future__ import annotations

import asyncio
import queue

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from core.utils.ffmpeg_check import (
    describe_ffmpeg_status,
    ffmpeg_missing_message,
    find_ffmpeg,
)
from sidecar.schemas import ConfigUpdate, ConvertRequest, ScanRequest
from sidecar.session import SidecarSession


def create_app(session: SidecarSession | None = None) -> FastAPI:
    active_session = session or SidecarSession()
    app = FastAPI()

    @app.get('/api/health')
    def health() -> dict:
        return {'ok': True}

    @app.post('/api/scan')
    def scan(request: ScanRequest):
        return active_session.scan(request.paths, request.known_paths)

    @app.get('/api/config')
    def get_config() -> dict:
        return active_session.get_config()

    @app.put('/api/config')
    def put_config(update: ConfigUpdate) -> dict:
        try:
            return active_session.put_config(update.model_dump(exclude_none=True))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get('/api/ffmpeg-status')
    def ffmpeg_status() -> dict:
        if find_ffmpeg() is None:
            return {'available': False, 'message': ffmpeg_missing_message()}
        _, message = describe_ffmpeg_status()
        return {'available': True, 'message': message}

    @app.post('/api/convert')
    def convert(request: ConvertRequest) -> dict:
        try:
            active_session.start_convert(request.tasks)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {'ok': True}

    @app.post('/api/cancel')
    def cancel_all() -> dict:
        active_session.cancel_all()
        return {'ok': True}

    @app.post('/api/cancel/{task_id}')
    def cancel_task(task_id: str) -> dict:
        task_ids = {
            task['task_id']
            for task in active_session.batch_snapshot()['tasks']
        }
        if task_id not in task_ids:
            raise HTTPException(status_code=404, detail='unknown task_id')
        active_session.cancel_task(task_id)
        return {'ok': True}

    @app.get('/api/batch')
    def batch() -> dict:
        return active_session.batch_snapshot()

    @app.websocket('/ws')
    async def websocket_events(websocket: WebSocket) -> None:
        await websocket.accept()
        events = active_session.bus.subscribe()
        try:
            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=0.05)
                    if message['type'] == 'websocket.disconnect':
                        break
                except TimeoutError:
                    pass
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    continue
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            active_session.bus.unsubscribe(events)

    return app

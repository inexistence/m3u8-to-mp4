from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.session import SidecarSession


class SidecarWsTests(unittest.TestCase):
    def test_convert_emits_batch_finished(self) -> None:
        session = SidecarSession()
        client = TestClient(create_app(session))

        def fake_convert(self, stream_index=None, progress_callback=None, cancel_event=None):
            if progress_callback:
                progress_callback('merging', 1, 1)
                progress_callback('packaging', 1, 1)

        with patch('core.batch_convert.M3U8Converter.convert', new=fake_convert):
            with client.websocket_connect('/ws') as ws:
                res = client.post(
                    '/api/convert',
                    json={
                        'tasks': [{
                            'task_id': 't1',
                            'path': 'C:/fake/index.m3u8',
                            'selected_stream_index': 0,
                        }],
                    },
                )
                self.assertEqual(res.status_code, 200)
                types = []
                for _ in range(20):
                    msg = ws.receive_json()
                    types.append(msg['type'])
                    if msg['type'] == 'batch_finished':
                        break
                self.assertIn('batch_finished', types)


if __name__ == '__main__':
    unittest.main()

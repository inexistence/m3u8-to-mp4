from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from sidecar.app import create_app
from sidecar.session import SidecarSession


class SidecarApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = SidecarSession()
        self.client = TestClient(create_app(self.session))

    def test_health(self) -> None:
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'ok': True})

    def test_config_roundtrip(self) -> None:
        res = self.client.get('/api/config')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('max_parallel_conversions', body)
        body['max_parallel_conversions'] = 3
        put = self.client.put('/api/config', json=body)
        self.assertEqual(put.status_code, 200)
        self.assertEqual(put.json()['max_parallel_conversions'], 3)

    def test_batch_idle(self) -> None:
        res = self.client.get('/api/batch')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()['is_converting'])


if __name__ == '__main__':
    unittest.main()

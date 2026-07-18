from __future__ import annotations

import unittest

from sidecar.events import EventBus


class EventBusTests(unittest.TestCase):
    def test_publish_reaches_subscriber(self) -> None:
        bus = EventBus()
        q = bus.subscribe()
        bus.publish({'type': 'task_progress', 'task_id': 'a'})
        self.assertEqual(q.get_nowait(), {'type': 'task_progress', 'task_id': 'a'})
        bus.unsubscribe(q)


if __name__ == '__main__':
    unittest.main()

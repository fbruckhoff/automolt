import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automolt.models.automation import QueueItem
from automolt.persistence import automation_store
from automolt.persistence.automation_store import BehaviorSubmoltRuntimeState


class AutomationStoreRuntimeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.handle = "agent-test"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_runtime_state_roundtrip(self) -> None:
        automation_store.init_db(self.base_path, self.handle)

        initial = automation_store.load_behavior_submolt_runtime_state(self.base_path, self.handle)
        self.assertIsNone(initial.behavior_submolt_policy_json)

        expected = BehaviorSubmoltRuntimeState(
            behavior_submolt_mtime_ns=123,
            behavior_submolt_size=456,
            behavior_submolt_policy_json='{"enabled":true}',
            behavior_submolt_loaded_at_utc="2026-03-17T10:00:00+00:00",
        )
        automation_store.save_behavior_submolt_runtime_state(self.base_path, self.handle, expected)

        loaded = automation_store.load_behavior_submolt_runtime_state(self.base_path, self.handle)
        self.assertEqual(expected.behavior_submolt_mtime_ns, loaded.behavior_submolt_mtime_ns)
        self.assertEqual(expected.behavior_submolt_size, loaded.behavior_submolt_size)
        self.assertEqual(expected.behavior_submolt_policy_json, loaded.behavior_submolt_policy_json)
        self.assertEqual(expected.behavior_submolt_loaded_at_utc, loaded.behavior_submolt_loaded_at_utc)

    def test_queue_item_author_name_roundtrip(self) -> None:
        automation_store.init_db(self.base_path, self.handle)
        item = QueueItem(
            item_id="post-1",
            item_type="post",
            post_id="post-1",
            submolt_name="alpha",
            author_name="other-agent",
            created_at=datetime.now(timezone.utc),
        )
        automation_store.insert_items(self.base_path, self.handle, [item])

        pending = automation_store.list_items(self.base_path, self.handle, "pending-analysis", limit=5)

        self.assertEqual(1, len(pending))
        self.assertEqual("other-agent", pending[0].author_name)


if __name__ == "__main__":
    unittest.main()

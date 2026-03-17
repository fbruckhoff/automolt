import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

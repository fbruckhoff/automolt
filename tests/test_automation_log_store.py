import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automolt.persistence import automation_log_store
from automolt.persistence.automation_log_store import AutomationEventStatus


class AutomationLogStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.handle = "agent-test"
        (self.base_path / ".agents" / self.handle).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_and_list_events(self) -> None:
        now = datetime.now(timezone.utc)
        automation_log_store.write_automation_event(
            self.base_path,
            self.handle,
            event_type="create_submolt",
            source_trigger="scheduled",
            status=AutomationEventStatus.SUCCESS,
            created_at_utc=now - timedelta(hours=2),
            submolt_name="alpha-lab",
        )
        automation_log_store.write_automation_event(
            self.base_path,
            self.handle,
            event_type="create_post",
            source_trigger="scheduled",
            status=AutomationEventStatus.SUCCESS,
            created_at_utc=now - timedelta(hours=1),
            submolt_name="alpha-lab",
            post_id="post-1",
        )

        events = automation_log_store.list_automation_events(self.base_path, self.handle)

        self.assertEqual(2, len(events))
        self.assertEqual("create_post", events[0].event_type)
        self.assertEqual("create_submolt", events[1].event_type)

    def test_successful_submolt_helpers(self) -> None:
        now = datetime.now(timezone.utc)
        automation_log_store.write_automation_event(
            self.base_path,
            self.handle,
            event_type="create_submolt",
            source_trigger="scheduled",
            status=AutomationEventStatus.SUCCESS,
            created_at_utc=now - timedelta(hours=1),
            submolt_name="alpha-lab",
        )
        automation_log_store.write_automation_event(
            self.base_path,
            self.handle,
            event_type="create_submolt",
            source_trigger="scheduled",
            status=AutomationEventStatus.FAILED,
            created_at_utc=now,
            submolt_name="beta-lab",
        )

        last_success = automation_log_store.get_last_successful_submolt_creation(self.base_path, self.handle)
        count_today = automation_log_store.count_successful_submolt_creations_since(
            self.base_path,
            self.handle,
            now.replace(hour=0, minute=0, second=0, microsecond=0),
        )

        self.assertIsNotNone(last_success)
        assert last_success is not None
        self.assertEqual("alpha-lab", last_success.submolt_name)
        self.assertEqual(1, count_today)
        self.assertTrue(automation_log_store.has_successful_submolt_name(self.base_path, self.handle, "alpha-lab"))
        self.assertFalse(automation_log_store.has_successful_submolt_name(self.base_path, self.handle, "beta-lab"))


if __name__ == "__main__":
    unittest.main()

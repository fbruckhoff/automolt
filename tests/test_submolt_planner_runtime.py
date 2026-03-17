import tempfile
import unittest
from pathlib import Path

from automolt.api.client import MoltbookClient
from automolt.models.llm import ActionPlan
from automolt.persistence import prompt_store
from automolt.services.automation_service import AutomationService


class SubmoltPlannerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.handle = "agent-test"
        self.api_client = MoltbookClient(base_url="http://localhost")
        self.service = AutomationService(api_client=self.api_client, base_path=self.base_path)

    def tearDown(self) -> None:
        self.api_client.close()
        self.temp_dir.cleanup()

    def test_reload_submolt_policy_parses_frontmatter(self) -> None:
        prompt_store.write_prompt(
            self.base_path,
            self.handle,
            "behavior_submolt",
            """---
submolt_enabled: true
submolt_create_interval_hours: 3
submolt_max_creations_per_day: 2
submolt_topic_policy: focus on testing
submolt_allowed_topics: tests, quality
submolt_name_prefix: lab
---
Create communities about testing tools.
""",
        )

        policy = self.service.reload_submolt_policy(self.handle)

        self.assertTrue(policy.enabled)
        self.assertEqual(3, policy.interval_hours)
        self.assertEqual(2, policy.max_creations_per_day)
        self.assertEqual("focus on testing", policy.topic_policy)
        self.assertEqual(("tests", "quality"), policy.allowed_topics)
        self.assertEqual("lab", policy.name_prefix)

    def test_reload_submolt_policy_rejects_invalid_policy(self) -> None:
        prompt_store.write_prompt(
            self.base_path,
            self.handle,
            "behavior_submolt",
            """---
submolt_create_interval_hours: 0
---
invalid
""",
        )

        with self.assertRaises(ValueError):
            self.service.reload_submolt_policy(self.handle)

    def test_action_plan_supports_reactive_escalation_fields(self) -> None:
        plan = ActionPlan.model_validate(
            {
                "reply_text": "  hello world  ",
                "upvote": True,
                "promote_to_submolt": True,
                "promotion_topic": "  tooling  ",
            }
        )

        self.assertEqual("hello world", plan.reply_text)
        self.assertTrue(plan.upvote)
        self.assertTrue(plan.promote_to_submolt)
        self.assertEqual("tooling", plan.promotion_topic)


if __name__ == "__main__":
    unittest.main()

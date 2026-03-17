import tempfile
import unittest
from pathlib import Path

from automolt.api.client import MoltbookAPIError, MoltbookClient
from automolt.models.llm import ActionPlan
from automolt.models.submolt import SubmoltCreateResponse
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

    def test_normalize_planned_submolt_name_enforces_api_constraints(self) -> None:
        normalized = self.service._normalize_planned_submolt_name(
            "Sleep Quality And Focus Weekly Discussions",
            "rainlayer",
        )

        self.assertIsNotNone(normalized)
        if normalized is None:
            self.fail("Expected normalized planner submolt name")
        self.assertTrue(normalized.startswith("rainlayer-"))
        self.assertLessEqual(len(normalized), 30)
        self.assertRegex(normalized, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def test_create_planned_submolt_with_retry_retries_on_bad_request(self) -> None:
        class _RetryingSubmoltService:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def create_submolt(
                self,
                api_key: str,
                name: str,
                display_name: str,
                description: str | None = None,
                allow_crypto: bool = False,
            ) -> SubmoltCreateResponse:
                self.calls.append(name)
                if len(self.calls) == 1:
                    raise MoltbookAPIError(message="Bad Request", status_code=400)

                return SubmoltCreateResponse(
                    name=name,
                    display_name=display_name,
                    description=description,
                    created_at="2026-03-17T00:00:00Z",
                    allow_crypto=allow_crypto,
                )

        retrying_service = _RetryingSubmoltService()
        self.service._submolt_service = retrying_service

        result = self.service._create_planned_submolt_with_retry(
            api_key="api-key",
            submolt_name="rainlayer-sleep-quality-focus",
            display_name="Rainlayer Sleep Quality Focus",
            description="A community for sleep-quality and focus discussions.",
            allow_crypto=False,
        )

        self.assertEqual(2, len(retrying_service.calls))
        self.assertNotEqual(retrying_service.calls[0], retrying_service.calls[1])
        self.assertEqual(result.name, retrying_service.calls[1])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from automolt.cli import cli
from automolt.models.agent import Agent, AgentConfig, Automation, VerificationStatus
from automolt.models.client import ClientConfig
from automolt.models.llm_provider import LLMProviderConfig, OpenAIProviderConfig
from automolt.persistence import agent_store, prompt_store, system_prompt_store
from automolt.persistence.client_store import save_client_config


class AutomationSetupCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.handle = "agent-test"

    def _prepare_workspace(
        self,
        base_path: Path,
        *,
        search_query: str | None,
        openai_api_key: str | None,
        create_required_prompts: bool,
    ) -> None:
        provider_config = LLMProviderConfig(openai=OpenAIProviderConfig(api_key=openai_api_key))
        save_client_config(base_path, ClientConfig(llm_provider_config=provider_config))

        agent_config = AgentConfig(
            agent=Agent(
                handle=self.handle,
                description="Test agent",
                verification_status=VerificationStatus.VERIFIED,
                is_active=True,
            ),
            automation=Automation(search_query=search_query),
        )
        agent_store.save_agent_config(base_path, agent_config)

        system_prompt_store.ensure_system_prompt_file(base_path, "filter")
        system_prompt_store.ensure_system_prompt_file(base_path, "action")

        if create_required_prompts:
            prompt_store.write_prompt(base_path, self.handle, "filter", "filter prompt content")
            prompt_store.write_prompt(base_path, self.handle, "behavior", "behavior prompt content")

    def test_setup_help_includes_behavior_submolt_flag(self) -> None:
        result = self.runner.invoke(cli, ["automation", "setup", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--behavior-submolt-md", result.output)

    def test_atomic_behavior_submolt_flag_writes_prompt_file(self) -> None:
        with self.runner.isolated_filesystem():
            base_path = Path.cwd()
            self._prepare_workspace(
                base_path,
                search_query=None,
                openai_api_key=None,
                create_required_prompts=False,
            )

            with patch(
                "automolt.commands.automation.setup_command.click.launch",
                side_effect=lambda file_path: Path(file_path).write_text("submolt policy prompt content", encoding="utf-8"),
            ), patch(
                "automolt.commands.automation.setup_command.click.pause"
            ):
                result = self.runner.invoke(
                    cli,
                    [
                        "automation",
                        "setup",
                        "--handle",
                        self.handle,
                        "--behavior-submolt-md",
                    ],
                )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("--behavior-submolt-md", result.output)
            self.assertEqual(
                "submolt policy prompt content",
                prompt_store.read_prompt(base_path, self.handle, "behavior_submolt"),
            )

    def test_success_output_includes_behavior_submolt_status(self) -> None:
        with self.runner.isolated_filesystem():
            base_path = Path.cwd()
            self._prepare_workspace(
                base_path,
                search_query="agentic ai",
                openai_api_key="sk-test1234",
                create_required_prompts=True,
            )

            with patch(
                "automolt.commands.automation.setup_command.click.launch",
                side_effect=lambda file_path: Path(file_path).write_text("submolt planner behavior content", encoding="utf-8"),
            ), patch(
                "automolt.commands.automation.setup_command.click.pause"
            ):
                result = self.runner.invoke(
                    cli,
                    [
                        "automation",
                        "setup",
                        "--handle",
                        self.handle,
                        "--behavior-submolt-md",
                    ],
                )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Automation Setup Complete", result.output)
            self.assertIn("BEHAVIOR_SUBMOLT.md", result.output)


if __name__ == "__main__":
    unittest.main()

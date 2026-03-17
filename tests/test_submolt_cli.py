import unittest

from click.testing import CliRunner

from automolt.cli import cli


class SubmoltCliHelpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_submolt_group_shows_help_when_invoked_without_subcommand(self) -> None:
        result = self.runner.invoke(cli, ["submolt"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Manage submolts (communities) on Moltbook.", result.output)
        self.assertIn("create", result.output)
        self.assertIn("post", result.output)

    def test_submolt_create_help_lists_new_options(self) -> None:
        result = self.runner.invoke(cli, ["submolt", "create", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--name", result.output)
        self.assertIn("--display-name", result.output)
        self.assertIn("--description", result.output)
        self.assertIn("--allow-crypto", result.output)

    def test_submolt_post_help_lists_post_options(self) -> None:
        result = self.runner.invoke(cli, ["submolt", "post", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("SUBMOLT_NAME", result.output)
        self.assertIn("--title", result.output)
        self.assertIn("--content", result.output)
        self.assertIn("--url", result.output)


if __name__ == "__main__":
    unittest.main()

"""Entry point for the Automolt CLI."""

import sys

from automolt.cli import cli


def main() -> None:
    """Run the Automolt CLI."""
    cli()


if __name__ == "__main__":
    sys.exit(main())

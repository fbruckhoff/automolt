.PHONY: dev-setup

dev-setup:
	uv sync --dev
	uv run pre-commit install --hook-type commit-msg
	uv tool install --editable --reinstall .

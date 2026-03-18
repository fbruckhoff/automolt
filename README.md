# 🦞 Automolt CLI — Agentic Workflow Engine for Moltbook

![Automolt CLI Banner](banner.webp)

<p align="center">
  <a href="https://github.com/fbruckhoff/automolt/actions/workflows/ci.yml?branch=main"><img src="https://img.shields.io/github/actions/workflow/status/fbruckhoff/automolt/ci.yml?branch=main&style=flat" alt="CI status"></a>
  <a href="https://github.com/fbruckhoff/automolt/releases"><img src="https://img.shields.io/github/v/release/fbruckhoff/automolt?include_prereleases&style=flat" alt="GitHub release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="MIT License"></a>
</p>

A command-line client for [Moltbook](https://www.moltbook.com), built for agent-centric workflows: identity management, semantic discovery, posting interactions, and stage-routed automation.

- Repository: `https://github.com/fbruckhoff/automolt`
- Language/runtime: Python 3.14.3+
- CLI entry point: `automolt`

## Why Automolt CLI

Automolt CLI is designed for operators who want a local-first workflow with explicit control over:

- agent identity and session targeting,
- content interaction (`search`, `comment`, `upvote`),
- automation configuration and scheduler lifecycle,
- auditable prompt/response traces for automation stages.

## Installation

### Prerequisites

- Python 3.14.3+
- [uv](https://docs.astral.sh/uv/)
- OpenAI API key

### Install from source

```bash
git clone https://github.com/fbruckhoff/automolt
cd automolt
uv tool install --editable --reinstall .
```

> [!TIP]
> `--editable` keeps the installed command linked to your local checkout, so source edits are reflected immediately.

## Quickstart

### 1) Initialize a client workspace (separate from this repo)

```bash
mkdir my-automolt-workspace
cd my-automolt-workspace
automolt init
```

Initialization creates client-root state and prompt contracts:

- `.agents/`
- `.sessions/`
- `client.json`
- `FILTER_SYS.md`
- `ACTION_SYS.md`

### 2) Register your agent

```bash
automolt signup
```

Then complete verification on Moltbook and confirm status:

```bash
automolt profile
```

### 3) Select your active agent

```bash
automolt agents
```

This sets your **active agent** for the current session. Once selected, all commands run relative to this agent unless you explicitly specify `--handle`.

### 4) Configure automation

```bash
automolt automation setup
```

This sets query/cutoff, per-agent prompt files (`FILTER.md`, `BEHAVIOR.md`), and stage LLM provider/model routing.

### 5) Run automation

Foreground:

```bash
automolt automation start
```

Background (launchd, macOS only):

```bash
automolt automation start --background
```

Control and observe runtime:

```bash
automolt automation status
automolt automation monitor
automolt automation stop
```

## CLI Capability Matrix

| Command | Purpose | Key Options / Notes |
| :--- | :--- | :--- |
| `automolt init` | Initialize a client workspace in current directory | Creates `.agents/`, `.sessions/`, `client.json`, `FILTER_SYS.md`, `ACTION_SYS.md` |
| `automolt signup` | Register a new Moltbook agent | Interactive handle check + local persistence |
| `automolt agents` | List/select active local agent | Updates session active agent + remembered `last_active_agent` |
| `automolt profile` | Show target agent profile | `--handle` optional (uses active agent if not specified) |
| `automolt profile update-description` | Update target agent description | Interactive prompt with validation; `--handle` optional |
| `automolt search <query>` | Semantic search posts/comments | `--type`, `--limit`, `--sort`, `--fetch-full-text`, `--max-chars`, `--handle` optional |
| `automolt comment` | Post comment or reply | `--post-id`, `--content`, optional `--parent-id`, `--handle` optional |
| `automolt upvote <target>` | Upvote post/comment by ID or URL | `--type auto\|post\|comment`, `--handle` optional |
| `automolt submolt create` | Create a submolt community | `--name`, `--display-name`, optional `--description`, `--allow-crypto`, `--handle`; auto-verifies pending publication challenges |
| `automolt submolt post <submolt_name>` | Create a post inside a submolt | `--title` required, exactly one of `--content` or `--url`, `--handle`; auto-verifies pending publication challenges |
| `automolt automation setup` | Configure automation state for one agent | `--provider`, `--api-key`, `--max-output-tokens`, `--filter-md`, `--behavior-md`, `--handle` optional |
| `automolt automation list` | Inspect automation queue by status | `--status all\|pending-analysis\|pending-action\|acted`, `--limit`, `--handle` optional |
| `automolt automation tick` | Run one scheduler tick immediately | `--dry`, `--handle` optional |
| `automolt automation start` | Start automation runtime | Foreground default; `--background` for launchd on macOS only; `--dry` for foreground simulation; `--handle` optional |
| `automolt automation stop` | Stop runtime and unload background scheduler if present | `--handle` optional |
| `automolt automation status` | Show runtime status snapshot | `--handle` optional |
| `automolt automation monitor` | Stream runtime monitoring output | `--handle` optional |

## Contributing

Contributions are welcome.

For contribution workflow, development setup, commit conventions (based on [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)), allowed scopes, and release steps, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Security and operational notes

- Treat `client.json` and agent API keys as sensitive.
- Keep your runtime client workspace separate from the source repository.
- Prefer HTTPS URLs and trusted environments for automation operations.

---

> **Disclaimer:** The Automolt CLI is an independent open source project and is not affiliated with, endorsed by, or associated with Moltbook or Moltbook.com in any way.

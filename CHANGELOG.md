## v0.10.0 (2026-03-17)

### build

- add v prefix to tag format for GitHub conventions

### chore

- remove duplicate workflow file

### ci

- add intelligent path filtering to skip runs on docs-only changes

### docs

- add submolt autonomy analysis and design documentation
- **cli**: update submolt command documentation
- **agents**: add file move and rename operations rule
- restructure documentation and add architecture guidance
- update README with active agent concept and prerequisites
- update SemVer policy to require v prefix for tags

### feat

- **submolts**: add submolt service integration with automation system
- **automation**: implement submolt autonomy runtime system
- **api**: enhance client and post service for submolt support
- **api**: add content verification service for Moltbook challenges
- **submolts**: add enhanced submolt creation and management

### refactor

- **cli**: update commands for submolt compatibility
- **automation**: update services for submolt integration
- archive PLANS-UPD.md as completed ExecPlan

### test

- add comprehensive test coverage for submolt functionality

## v0.9.2 (2026-02-27)

### build

- update dependencies and project configuration

### chore

- remove .DS_Store files from source control
- add MIT license
- ignore reports directory in gitignore
- remove .DS_Store file

### ci

- add GitHub Actions workflow for ruff checks

### docs

- add CI and release badges to README
- update title and add disclaimer
- add banner and enhance README title
- remove baseline tag instructions
- add Windsurf IDE integration instructions
- update project documentation for contributor workflow
- improve README.md

### feat

- **automation**: add pending-action retry mechanism and improve monitoring

### fix

- **scheduler**: resolve launchd timing to prevent missed cycles
- **cli**: map --dry option to dry_run in automation tick

### refactor

- reorganize workspace from .windsurf to .agents

---
description: Execute commit strategy
---

IMPORTANT: Commit messages must strictly follow the ruleset under `rules/git.md` and `CONTRIBUTIONS.md`.

- Before making any commit, study the rules and instructions in `rules/git.md` and `CONTRIBUTIONS.md`.
	- Perform any required checks. If they do not pass, abort and inform the user.

- Determine whether there are any staged files.

- If there are staged files, exclusively focus on the staged files.
	- Do not stage any other files.
	- Analyze the changes and generate an apropriate commit message.
	- When done, make the commit.
	- After making the commit, stop. Do not stage other files.

- If there are no staged files, analayze the unstaged changes.
	- Sequentially and strategically group changes into meaningful commits following the scoping rules, commit message rules.
	- For each group, stage the relevant changes, generate an appropriate commit message and make the commit.
	- Continue until all changes are staged and committed.

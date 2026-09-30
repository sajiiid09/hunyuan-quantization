# CLAUDE.md — Conventions for AI agents

This file applies to every AI agent working in this repository, in any session, on any
machine. The same content is in `AGENTS.md`.

## Always do

1. **Read the spec first.** `docs/superpowers/specs/2026-09-30-raco-gen-design.md` is the
   source of truth for architecture, decisions and constraints.
2. **Update docs when decisions change.** If a session changes architecture, models,
   endpoints, or constraints, update the spec (or PLAN.md) before finishing.
3. **Record performance, bottlenecks and improvements.** Append a row to `docs/LOG.md`
   for every session that measures or changes anything. Format below.
4. **Commit before and after significant work.** Never leave the repo in a broken state.

## Never do

- Do not install models into VRAM permanently — one model group resident at a time.
- Do not touch existing services on ports 22, 5432, 7070, 8554, 8888, 8889, 631.
- Do not commit `models/`, `jobs/`, `.env`, or any secrets.
- Do not modify the spec's hardware constraints (section 2) without user approval.
- Do not reintroduce the HunyuanImage-3.0 quant track or the FastAPI gateway without
  explicit user approval.

## docs/LOG.md format

Append one row per session:

```markdown
| 2026-10-01 | Phase 0 complete | — | PCIe 3.0 bus-bound weight streaming | Root docs written, repo initialized |
```

Columns: `Date | Session focus | Performance measured | Bottlenecks found | Improvements made`

Use `—` when a column has no entry. Keep it brief — one line per session.

## Repo topology

- **Server** (`raco-ai@100.66.198.27:~/Documents/raco-gen`) — canonical, has the full
  history. All model installs and service changes happen here.
- **Local** (`~/Documents/raco-gen` on the working machine) — clone of the server repo.
  Used for editing docs, reviewing code, and planning. Sync with `git pull` / `git push`
  over SSH.

To push local changes to the server:

```bash
cd ~/Documents/raco-gen
git push ssh://raco-ai@100.66.198.27/home/raco-ai/Documents/raco-gen main
```

To pull server changes:

```bash
git pull ssh://raco-ai@100.66.198.27/home/raco-ai/Documents/raco-gen main
```

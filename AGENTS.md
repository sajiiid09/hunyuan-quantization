# AGENTS.md — raco-gen agent guide

Same content as `CLAUDE.md`. Both files must stay in sync.

## Summary

raco-gen is a self-hosted image/video generation server on a 12 GB RTX 4070 Ti, exposed
through `https://gen.sajiid.me` via ComfyUI's web UI and native API. The full design spec
is at `docs/superpowers/specs/2026-09-30-raco-gen-design.md`.

## Agent rules

1. Read the spec before making changes.
2. Update relevant docs when decisions change.
3. Append to `docs/LOG.md` every session — performance, bottlenecks, improvements.
4. Commit before and after significant work.
5. Never commit secrets, models, or job data.
6. Do not reintroduce the HunyuanImage-3.0 quant track or the FastAPI gateway without
   explicit user approval.

## Key paths

| Path | Purpose |
|---|---|
| `docs/superpowers/specs/2026-09-30-raco-gen-design.md` | Full design spec |
| `PLAN.md` | Implementation phases and status |
| `CHANGELOG.md` | Human-readable change history |
| `docs/LOG.md` | Append-only performance/bottleneck log |
| `eval/prompts/` | Eval set (50 t2i, 15 edit, 12 i2v) |
| `models/` | Model weights (gitignored) |

## Repo sync

```bash
# Push local → server
git push ssh://raco-ai@100.66.198.27/home/raco-ai/Documents/raco-gen main

# Pull server → local
git pull ssh://raco-ai@100.66.198.27/home/raco-ai/Documents/raco-gen main
```

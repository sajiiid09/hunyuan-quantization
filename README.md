# raco-gen

Self-hosted image & video generation server. Runs on a single RTX 4070 Ti (12 GB) and is
reachable from anywhere through ComfyUI's web UI and native API at
`https://gen.sajiid.me`. The server is headless; clients connect via browser or
programmatic API with no local model execution.

## What it does

| Task | Model | Status |
|---|---|---|
| Text → image | FLUX.1 [dev] (GGUF Q5_K_M) + realism LoRAs | ✅ Ready to install |
| Image edit / inpaint | FLUX.1 Fill [dev] (GGUF Q5_K_M) | ✅ Ready to install |
| Image → video (primary) | Wan 2.1 I2V 14B (GGUF Q4_K_M) | ✅ Ready to install |
| Image → video (fast preview) | HunyuanVideo-1.5 480P I2V Step-Distilled (Q6_K) | ✅ Ready to install |
| Text → video | HunyuanVideo-1.5 480P T2V CFG-distilled (Q6_K) | ✅ Ready to install |
| Talking head / avatar | HunyuanVideo-Avatar (TeaCache) | ✅ Ready to install |

## Architecture

```
Browser / API client
        │
        ▼
Cloudflare Tunnel (gen.sajiid.me, HTTP/2)
        │
        ▼
ComfyUI (0.0.0.0:8188)
  FLUX.1 [dev] · Wan 2.1 I2V · HunyuanVideo-1.5 · Avatar
```

- **ComfyUI** — the only public-facing process. Web UI, native API, WebSocket progress.
- **cloudflared** — named tunnel to `gen.sajiid.me`. No router ports opened.
- No gateway, no job queue, no custom routes. ComfyUI is the entire backend.

## Quick start

```bash
# Server
ssh raco-ai@100.66.198.27
systemctl status raco-gen-comfyui raco-gen-cloudflared

# API
curl -X POST https://gen.sajiid.me/prompt \
     -H 'Content-Type: application/json' \
     -d @workflow_api.json

# WebSocket progress
wscat -c wss://gen.sajiid.me/ws
```

## Repository layout

```
├── docs/superpowers/specs/2026-09-30-raco-gen-design.md  # full design spec
├── eval/prompts/          # 50 t2i + 15 edit + 12 i2v tasks with yes/no checks
├── docs/LOG.md            # append-only performance / bottleneck / improvement log
├── models/                # all weights + MANIFEST.md (gitignored)
└── CLAUDE.md / AGENTS.md  # agent conventions
```

## Key documents

- **Spec:** `docs/superpowers/specs/2026-09-30-raco-gen-design.md`
- **Plan:** `PLAN.md` — implementation phases and current status
- **Agent conventions:** `CLAUDE.md`, `AGENTS.md`
- **Changelog:** `CHANGELOG.md`
- **Performance log:** `docs/LOG.md`

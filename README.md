# raco-gen

Self-hosted image & video generation server. Runs on a single RTX 4070 Ti (12 GB) and is
reachable from anywhere through `https://gen.sajiid.me` with a fixed API key.

## What it does

| Task | Stopgap model | Status |
|---|---|---|
| Text → image | HunyuanImage-2.1 Distilled (GGUF Q5_K_M) | ✅ Serving |
| Image edit | Qwen-Image-Edit (GGUF Q4_K_M) + Lightning LoRA | ✅ Serving |
| Text → video | HunyuanVideo-1.5 480p T2V CFG-distilled (Q6_K) | ✅ Serving |
| Image → video | HunyuanVideo-1.5 480p I2V step-distilled (Q6_K) | ✅ Serving |
| HunyuanImage-3.0 | Custom 2–3 bit quant (section 8 of spec) | 🔬 R&D |

## Architecture

```
ComfyUI (client PC) ──┐
                      ├──► Cloudflare Tunnel ──► Gateway (FastAPI) ──► ComfyUI (local)
Open WebUI ───────────┘    gen.sajiid.me         queue · API key      + Image3 worker
```

- **ComfyUI** — inference engine, localhost only.
- **Gateway** — the only public process. API key, job queue, templates, 1 h TTL.
- **cloudflared** — named tunnel to `gen.sajiid.me` (HTTP/2, no QUIC).
- **Image3 worker** — custom weight-streaming loader for the quantized HunyuanImage-3.0.

## Quick start

```bash
# Server (already running)
ssh raco-ai@100.66.198.27
systemctl status raco-gen-gateway raco-gen-comfyui raco-gen-cloudflared

# API
curl -H "X-API-Key: $RACO_API_KEY" -F task=image.generate \
     -F prompt="a cat" -F aspect=1:1 https://gen.sajiid.me/v1/jobs
```

## Repository layout

```
├── docs/superpowers/specs/2026-09-30-raco-gen-design.md  # full design spec
├── eval/prompts/          # 50 t2i + 15 edit + 12 i2v tasks with yes/no checks
├── docs/LOG.md            # append-only performance / bottleneck / improvement log
├── models/                # all weights + MANIFEST.md (gitignored)
├── jobs/                  # per-job folders, 1 h TTL (gitignored)
└── CLAUDE.md / AGENTS.md  # agent conventions
```

## Key documents

- **Spec:** `docs/superpowers/specs/2026-09-30-raco-gen-design.md`
- **Plan:** `PLAN.md` — implementation phases and current status
- **Agent conventions:** `CLAUDE.md`, `AGENTS.md`
- **Changelog:** `CHANGELOG.md`
- **Performance log:** `docs/LOG.md`

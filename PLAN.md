# PLAN — raco-gen implementation phases

Last updated: 2026-10-01

## Phase 0 — Documentation & repo setup ✅

- [x] Design spec written and approved (`docs/superpowers/specs/2026-09-30-raco-gen-design.md`)
- [x] Eval prompt set written (`eval/prompts/`: 50 t2i, 15 edit, 12 i2v)
- [x] Root docs written (README, CLAUDE, AGENTS, PLAN, CHANGELOG, LOG)
- [x] Git repo initialized on server and cloned to local
- [x] Architecture pivoted: HunyuanImage-3.0 quant → FLUX.1 [dev] + Wan 2.1 I2V
- [x] Gateway removed; tunnel → ComfyUI directly

## Phase 1 — ComfyUI + model installation

- [x] Install ComfyUI (pinned commit) + uv venv on server — v0.38.0, torch 2.11.0+cu130
- [x] Install ComfyUI-GGUF + ComfyUI-WanVideoWrapper custom nodes
- [ ] Download FLUX.1 [dev] GGUF Q5_K_M + text encoders + VAE — clip_l, ae, loras verified; flux-dev, flux-t5 stalled on SHA check
- [x] Download Wan 2.1 I2V 14B GGUF Q4_K_M (480p + 720p) + CLIP Vision + VAE + UMT5 — all 5 files (~30.8 GB) verified & live in ComfyUI
- [ ] Download HunyuanVideo-1.5 480P T2V CFG-distilled — qwen, byt5, vae, sigclip verified; hunyuan-t2v at 28%
- [ ] Download HunyuanVideo-Avatar + TeaCache workflow — not in manifest (deferred)
- [x] Download uncensored/realism LoRAs for FLUX — flux-realism-xlabs, flux-super-realism
- [x] Write ComfyUI workflow templates for each task (API format) — workflows/{flux-t2i,wan-i2v,hunyuan-t2v}.json
- [x] Set up cloudflared named tunnel to gen.sajiid.me — live, gen.sajiid.me → 200
- [x] systemd units for ComfyUI + cloudflared — both enabled + active
- [ ] Smoke tests: each task end to end, record time and peak VRAM

## Phase 2 — Client access

- [ ] Browser access test from desktop (192.168.10.6)
- [ ] Programmatic API test (POST /prompt + WebSocket)
- [ ] External test through gen.sajiid.me from another network

## Phase 3 — Evaluation & tuning

- [ ] Run full eval suite (50 t2i + 15 edit + 12 i2v) with FLUX + Wan
- [ ] Qwen2.5-VL scoring of all eval items
- [ ] Tune LoRA weights, sampling settings, VRAM usage
- [ ] Record performance baseline in docs/LOG.md

## Phase 4 — Production hardening

- [ ] 24 h cleanup cron for ComfyUI output/input/temp
- [ ] Optional: Cloudflare Access for edge authentication
- [ ] update.sh script for pinned upgrades + smoke tests + rollback
- [ ] Document operational procedures

## Current status

Phase 1 in progress. ComfyUI 0.38.0 + custom nodes + tunnel + systemd are done.
Model download running (HF CDN throttles the server to ~5 MB/s; ~30 GB left).
Client (`scripts/client/raco_gen.py`) keeps all generations on the local machine.
Next: finish downloads → smoke tests → Phase 2.

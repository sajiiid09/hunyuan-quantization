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

- [ ] Install ComfyUI (pinned commit) + uv venv on server
- [ ] Install ComfyUI-GGUF + ComfyUI-WanVideoWrapper custom nodes
- [ ] Download FLUX.1 [dev] GGUF Q5_K_M + text encoders + VAE
- [ ] Download Wan 2.1 I2V 14B GGUF Q4_K_M (480p + 720p) + CLIP Vision + VAE
- [ ] Download HunyuanVideo-1.5 480P I2V Step-Distilled + T2V CFG-distilled
- [ ] Download HunyuanVideo-Avatar + TeaCache workflow
- [ ] Download uncensored/realism LoRAs for FLUX
- [ ] Write ComfyUI workflow templates for each task (API format)
- [ ] Set up cloudflared named tunnel to gen.sajiid.me
- [ ] systemd units for ComfyUI + cloudflared
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

Phase 0 complete. Next: Phase 1 — install ComfyUI and all models on the server.

# PLAN — raco-gen implementation phases

Last updated: 2026-10-01

## Phase 0 — Documentation & repo setup ✅

- [x] Design spec written and approved (`docs/superpowers/specs/2026-09-30-raco-gen-design.md`)
- [x] Eval prompt set written (`eval/prompts/`: 50 t2i, 15 edit, 12 i2v)
- [x] Root docs written (README, CLAUDE, AGENTS, PLAN, CHANGELOG, docs/LOG)
- [x] Git repo initialized on server and cloned to local

## Phase 1 — Always-on stopgap stack

- [ ] Install ComfyUI (pinned commit) + uv venv
- [ ] Install stopgap models: HunyuanImage-2.1, Qwen-Image-Edit, HunyuanVideo-1.5 (T2V + I2V)
- [ ] Write ComfyUI workflow templates for each task
- [ ] Build gateway (FastAPI): API key, queue, templates, TTL sweeper
- [ ] Set up cloudflared named tunnel to gen.sajiid.me
- [ ] systemd units for all services
- [ ] Smoke tests (section 11 of spec)

## Phase 2 — Clients

- [ ] ComfyUI-RacoRemote node pack
- [ ] Open WebUI video tool
- [ ] External tests through gen.sajiid.me

## Phase 3 — HunyuanImage-3.0 custom quant (R&D, parallel)

- [ ] Stage 0: Produce reference images (Tencent hosted + T2I-CoReBench)
- [ ] Stage 1: Download BF16 Instruct-Distil weights (~169 GB)
- [ ] Stage 2: Error check HQQ vs SDNQ at 2/3/4 bits on sample layers
- [ ] Stage 3: L1 build — no pruning, untuned mixed 2/3-bit (~29 GB)
- [ ] Stage 4: Evaluate L1 against references
- [ ] Stage 5: Local profiling pass for pruning saliency (only if L1 fails)
- [ ] Stage 6: L2 build — 25% pruned, 3-bit experts (~28 GB) (only if L1 fails)
- [ ] Stage 7: Image3 worker runtime (weight streaming, CUDA stream prefetch)

## Phase 4 — Image3 swap-in

- [ ] Gateway routes image tasks to Image3 worker
- [ ] HunyuanImage-2.1 + Qwen-Image-Edit remain as automatic fallbacks
- [ ] Full eval suite passes with user approval

## Current status

Phase 0 complete. Next: Phase 1 — install ComfyUI and stopgap models on the server.

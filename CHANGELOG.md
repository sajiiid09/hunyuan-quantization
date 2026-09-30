# CHANGELOG — raco-gen

## 2026-10-01 — Architecture pivot

- **Removed** HunyuanImage-3.0 sub-3-bit quantization track (section 8). Untuned 2–3-bit
  quantization is at the known breaking point; calibration needs hardware this server
  doesn't have.
- **Removed** FastAPI gateway. Tunnel now maps directly to ComfyUI on 8188.
- **New image stack:** FLUX.1 [dev] GGUF Q5_K_M + uncensored/realism LoRAs.
- **New video stack:** Wan 2.1 I2V 14B Q4_K_M (primary), HunyuanVideo-1.5 (fast preview),
  HunyuanVideo-Avatar (talking heads).
- **New API:** ComfyUI native (POST /prompt, WebSocket /ws). No custom routes.
- **New retention:** 24 h cleanup cron instead of 1 h TTL sweeper.
- Root docs updated: README, PLAN, CLAUDE, AGENTS, CHANGELOG, LOG.

## 2026-09-30

- Design spec approved (13 sections). HunyuanImage-3.0 custom quant track defined.
- Eval prompt set written: 50 text-to-image, 15 edit, 12 image-to-video tasks.
- Cloudflare named tunnel decided: gen.sajiid.me over HTTP/2.

# raco-gen — Self-hosted image & video generation server

**Date:** 2026-09-30 (revised 2026-10-01)
**Status:** Design approved — architecture pivoted from HunyuanImage-3.0 quant to FLUX + Wan
**Host:** `raco-ai-server` (192.168.10.4, Tailscale 100.66.198.27)

## 1. Goal

Run image generation, image editing, text-to-video and image-to-video on `raco-ai-server`,
reachable from anywhere through ComfyUI's web UI and native API at `https://gen.sajiid.me`.
The server is headless; clients connect via browser or programmatic API from any machine
with no local model execution. The stack prioritizes photographic realism, anatomical
fidelity (including uncensored/NSFW human realism), and physical motion consistency.

### Out of scope

- 3D generation (Hunyuan3D), audio/Foley.
- 720p video and anything above 10 s (Wan 2.1 720p is the final-quality tier).
- Multi-user accounts, billing, per-user keys, a web gallery.
- Hardware changes (the RAM upgrade was considered and rejected).
- The HunyuanImage-3.0 sub-3-bit quantization track (abandoned — see section 8).

## 2. Hardware constraints (measured 2026-09-30)

| Item | Value | Consequence |
|---|---|---|
| GPU | RTX 4070 Ti, 12 GB, driver 595.91, CUDA 13 | Models run quantized with offload |
| System RAM | 32 GB (4×8 GB DDR4-3200, all slots used; board max 128 GB) | ~29 GB usable with desktop running; one model group loaded at a time |
| CPU / bus | Ryzen 5 5600G, PCIe 3.0 x16 | ~12 GB/s host→GPU; weight streaming is bus-bound |
| Disk | 512 GB NVMe, 401 GB free on `/` | Enough for all models |
| Desktop | GNOME stays running (user decision) | ~2 GB RAM and ~200 MB VRAM reserved for it |
| Existing services | Ports 22, 5432, 7070, 8554, 8888, 8889, 631 | Must not be touched |

## 3. Architecture

```
 Anywhere                                   raco-ai-server
┌──────────────────┐                      ┌───────────────────────────────────────────┐
│ Browser          │  HTTPS               │ cloudflared (systemd)                     │
│ (ComfyUI web UI) │──────┐               │     │                                     │
└──────────────────┘      │   Cloudflare  │     ▼                                     │
┌──────────────────┐      ├──► Tunnel ───►│ ComfyUI (0.0.0.0:8188)                    │
│ Programmatic API │──────┘ gen.sajiid.me  │  FLUX.1 [dev] · Wan 2.1 I2V · HV1.5       │
│ POST /prompt     │      │  HTTP/2        │  HunyuanVideo-Avatar                      │
└──────────────────┘      │                └───────────────────────────────────────────┘
                          │
                          ▼
                    WebSocket ws://gen.sajiid.me/ws
```

Units and their single responsibilities:

1. **ComfyUI.** The inference engine. It listens on `0.0.0.0:8188` and is the only
   public-facing process, reached exclusively through the Cloudflare tunnel. It serves the
   web UI, the native API (`POST /prompt`, `GET /prompt/{id}`, `GET /history/{id}`) and
   the WebSocket progress stream (`/ws`). ComfyUI-Manager is not installed.
2. **cloudflared.** A named Cloudflare Tunnel (`raco-gen`) mapping `gen.sajiid.me` to
   `127.0.0.1:8188`. The zone `sajiid.me` is already on Cloudflare nameservers, and `gen`
   is unused as of 2026-09-30. It runs with `--protocol http2`, because this network drops
   QUIC (UDP 7844). The server is authorised once with `cloudflared tunnel login`. No
   router ports are opened.

### Always-on behaviour

- ComfyUI and cloudflared run as systemd **system** services with `User=raco-ai`,
  `Restart=always`, and are enabled at boot.
- Sleep and suspend are disabled.
- The BIOS "Restore on AC power loss" option is set to *Power On*. This is a manual step
  for the user.
- A UPS is recommended but optional.

### Security

- ComfyUI binds to `0.0.0.0` but is only reachable through the Cloudflare tunnel.
- Cloudflare Access (optional) can add an authentication layer at the edge.
- No API key is enforced by ComfyUI itself; the tunnel is the trust boundary.
- Uploads are validated by ComfyUI's built-in image decoding.

## 4. Models and memory

| Task | Model | Quant | Approx. size |
|---|---|---|---|
| `image.generate` | FLUX.1 [dev] | GGUF Q5_K_M (fallback Q4_K_M) | ~12 GB |
| `image.edit` / inpaint | FLUX.1 Fill [dev] | GGUF Q5_K_M | ~12 GB |
| `video.i2v` (primary) | Wan 2.1 I2V 14B | GGUF Q4_K_M | ~9 GB |
| `video.i2v` (720p final) | Wan 2.1 I2V 14B 720P | GGUF Q4_K_M | ~9 GB |
| `video.i2v` (fast preview) | HunyuanVideo-1.5 480P I2V Step-Distilled | GGUF Q6_K | ~7 GB |
| `video.t2v` | HunyuanVideo-1.5 480P T2V CFG-distilled | GGUF Q6_K | ~7 GB |
| `avatar` | HunyuanVideo-Avatar | community TeaCache workflow | ~10 GB |
| Shared encoders | CLIP (clip_l + t5xxl), CLIP Vision, umt5_xxl, VAEs | FP8 / FP16 | ~15 GB |

### FLUX.1 [dev] realism strategy

- Base FLUX weights lack explicit anatomical tokens. Targeted uncensored/realism
  community LoRAs are applied at weights 0.7–1.0 to inject correct human anatomy, skin
  micro-textures, subsurface scattering, and natural lighting.
- Text encoders: dual CLIP loader with `clip_l.safetensors` and
  `t5xxl_fp8_e4m3fn.safetensors` (or `t5-v1_1-xxl-encoder-Q5_K_M.gguf`), offloaded to
  system RAM during sampling.
- VAE: standard `ae.safetensors`.

### Wan 2.1 I2V censorship mitigation

- Feeding an explicit, photorealistic FLUX frame into Wan 2.1 I2V bypasses text-encoder
  prompt filtering while leveraging Wan's superior soft-tissue dynamics, muscle
  deformation, and facial feature preservation.
- Conditioning: CLIP Vision (`clip_vision_h.safetensors`) + native `wan_2.1_vae.safetensors`.
- Target output: 3–5 s clips (81 frames at 16 fps). Drafts at 832×480, finals at 1280×720.

### Memory rules

- **One model group is resident at a time.** Switching groups reloads from NVMe, which
  costs about 10–30 s.
- Text encoders run first and are offloaded before the main model loads onto the GPU.
- Video decodes with tiled VAE.
- A video segment is **81 frames (~5 s at 16 fps)** by default. The limit rises to 121
  frames only if the smoke tests show peak VRAM ≤ 11.5 GB with no spill.
- Requests of 6–10 s are **chained**: segment 1 is T2V or I2V, and each later segment is
  I2V started from the previous segment's last frame with the same prompt and seed + n.
  The duplicate joining frame is dropped, and ffmpeg concatenates the segments to H.264
  MP4 at 24 fps without re-timing.

### Expected performance (targets to measure, not promises)

| Job | Target |
|---|---|
| Image generate (FLUX Q5_K_M, 25 steps) | 30–60 s |
| Image edit / inpaint | 30–90 s |
| 5 s 480p clip (Wan 2.1 I2V) | a few minutes |
| 10 s chained video | 2–3× a single clip |

## 5. API

ComfyUI's native API is the only interface. No gateway, no job queue, no custom routes.

### Web UI

- `https://gen.sajiid.me/` — ComfyUI's built-in web interface.
- Workflows are saved in ComfyUI's UI and can be loaded by any client.

### Programmatic API

| Method & path | Purpose |
|---|---|
| `POST /prompt` | Submit a workflow JSON. Returns `{"prompt_id": ...}`. |
| `GET /prompt/{prompt_id}` | Poll job status: `{"executions": [...]}`. |
| `GET /history/{prompt_id}` | Full execution history with outputs. |
| `GET /view?filename=...&type=output` | Download a result file. |
| `GET /queue` | Current queue state. |
| `DELETE /queue` | Cancel queued or running jobs. |
| `WS /ws` | WebSocket progress stream (prompt_id, steps, preview). |

### Client workflow

1. Author a workflow in ComfyUI's web UI (or import a saved JSON).
2. Use **Dev Mode → Save (API Format)** to get the API-ready JSON.
3. `POST /prompt` with that JSON to queue it.
4. Listen on `WS /ws` for progress, or poll `GET /prompt/{id}`.
5. Download outputs with `GET /view`.

## 6. Data flow and retention

1. ComfyUI writes outputs to `ComfyUI/output/`.
2. Files persist until manually deleted or cleaned by a cron job.
3. A daily cron job (`/etc/cron.d/raco-gen-cleanup`) deletes files older than 24 h from
   `ComfyUI/output/`, `ComfyUI/input/`, and `ComfyUI/temp/`.
4. No database, no job tracking, no prompt logging. ComfyUI's own history is the record.

## 7. Limits and error handling

| Condition | Behaviour |
|---|---|
| Upload not decodable as an image | ComfyUI returns `400` |
| CUDA out of memory | One automatic retry with safer settings (smaller VAE tiles, Q4 fallback for FLUX); then the job fails |
| Timeout (image 3 min, edit 4 min, video 8 min per segment) | Job fails; ComfyUI interrupted and VRAM freed |
| ComfyUI crashes | systemd restarts it; the client sees a connection error and retries |

Only one GPU job runs at a time (ComfyUI's built-in queue).

## 8. Model stack (post-pivot)

**Goal:** FLUX.1 [dev] for stills and inpainting, Wan 2.1 I2V 14B for primary video,
HunyuanVideo-1.5 for fast previews, HunyuanVideo-Avatar for talking heads.

### Why the pivot

The original plan (HunyuanImage-3.0 at 2–3 bits via custom quantization) was abandoned:

- No sub-4-bit build of HunyuanImage-3.0 exists that runs anywhere.
- Untuned 2–3-bit quantization sits at the known breaking point for diffusion models.
- Calibration needs ~190 GB RAM + an 80 GB GPU, which this server cannot provide.
- Pruning 25% of a 64-expert model cost Moonlight ~20% quality; the risk was too high.

FLUX.1 [dev] at Q5_K_M delivers comparable or better photographic realism with proven
GGUF tooling, and Wan 2.1 I2V 14B is a mature, well-supported video model.

### Image generation

- **Primary:** FLUX.1 [dev] GGUF Q5_K_M via ComfyUI-GGUF.
- **Sampling:** Euler / Simple, CFG 3.5, 25 steps.
- **LoRAs:** uncensored/realism community LoRAs at 0.7–1.0 weight.
- **Editing:** FLUX.1 Fill [dev] or inpainting nodes with differential diffusion.

### Video generation

- **Primary I2V:** Wan 2.1 I2V 14B GGUF Q4_K_M (480p drafts, 720p finals).
  - 30 steps, Flow Match Euler.
  - 81 frames at 16 fps (~5 s).
- **Fast preview:** HunyuanVideo-1.5 480P I2V Step-Distilled (8–12 steps).
- **T2V:** HunyuanVideo-1.5 480P T2V CFG-distilled.
- **Avatar:** HunyuanVideo-Avatar with TeaCache (~10 GB VRAM).

### Evaluation (every model change)

- Render `eval/prompts/t2i.jsonl` and `edit.jsonl` with fixed seeds.
- Qwen2.5-VL answers each item's `checks` (yes/no).
- Also record: text-rendering accuracy, seconds per image, peak VRAM and RAM.
- The `i2v.jsonl` tasks run on the image outputs to confirm they animate cleanly.
- **Pass = the user approves**, and each image takes ≤ 3 min.

## 9. Clients

### Browser (primary)

- Open `https://gen.sajiid.me/` in any browser.
- Use ComfyUI's web UI to author and run workflows.
- No local installation required.

### Programmatic API

- Any HTTP client can `POST /prompt` with a workflow JSON.
- Progress via WebSocket or polling.
- Outputs downloaded via `GET /view`.

### ComfyUI client packs (optional)

- Third-party ComfyUI node packs (e.g. ComfyUI-RacoRemote) can be installed on a client
  PC and pointed at `https://gen.sajiid.me` for node-based access.
- This is optional; the native API and web UI are sufficient.

## 10. Layout, security, updates

```
/home/raco-ai/Documents/raco-gen/
├── comfyui/            # ComfyUI checkout + uv venv (pinned commit)
│   └── models/
│       ├── diffusion_models/  (or unet/)
│       │   ├── flux1-dev-Q5_K_M.gguf
│       │   ├── flux1-fill-dev-Q5_K_M.gguf
│       │   ├── wan2.1-i2v-14b-480p-Q4_K_M.gguf
│       │   ├── wan2.1-i2v-720p-14b-Q4_K_M.gguf
│       │   └── hunyuan_video_1.5_480p_i2v_step_distilled.gguf
│       ├── clip/
│       │   ├── clip_l.safetensors
│       │   └── t5xxl_fp8_e4m3fn.safetensors
│       ├── clip_vision/
│       │   └── clip_vision_h.safetensors
│       ├── vae/
│       │   ├── ae.safetensors
│       │   └── wan_2.1_vae.safetensors
│       └── loras/
│           └── [flux_uncensored_realism_loras].safetensors
├── eval/prompts/       # 50 t2i + 15 edit + 12 i2v tasks
├── docs/
│   ├── superpowers/specs/2026-09-30-raco-gen-design.md
│   └── LOG.md
└── models/MANIFEST.md  # source URL + SHA-256 for each weight
```

- **Services run as `raco-ai`.** PyTorch is installed for CUDA 12.8+ via `uv`.
- **Custom nodes** are limited to those the workflows need (ComfyUI-GGUF,
  ComfyUI-WanVideoWrapper), each pinned to a commit.
- **Hardening:**
  - no ComfyUI-Manager;
  - ComfyUI binds to 0.0.0.0 but is only reachable through the tunnel;
  - uploads are validated by decoding;
  - Cloudflare Access (optional) adds edge authentication.
  - No firewall changes, to avoid disturbing existing services.
- **Updates:** `update.sh` pulls the pinned upgrades, re-runs the smoke tests, and rolls
  back on failure.

## 11. Testing

1. **Server smoke tests:**
   - each task end to end, recording time and peak VRAM;
   - a 10 s chained video;
   - a forced OOM retry;
   - a scan confirming no media remains after the 24 h cleanup cron.
2. **External tests** through `gen.sajiid.me` from another network: an image request with a
   wait longer than 100 s, and a video download.
3. **Client tests:**
   - browser access from the desktop (192.168.10.6);
   - programmatic API access with a simple Python script.

## 12. Evaluation set

Stored in the repo under `eval/prompts/`, each item with yes/no `checks` for the
Qwen2.5-VL judge:

- **`t2i.jsonl`: 50 prompts.** Run through FLUX.1 [dev] (GGUF Q5_K_M, Euler / Simple,
  CFG 3.5, 25 steps). Covers counting, spatial layout, attribute binding, text rendering,
  world knowledge, reasoning, negation, product, people, scene, style, infographic,
  long/complex prompts and cultural context. Items 49–50 are image-to-video sources.
- **`edit.jsonl`: 15 tasks.** Run through FLUX inpainting / instruction edit workflows.
  Instruction edits, restyles, same subject in a new scene, multi-reference and
  layout-keep edits. Their sources are `t2i` outputs.
- **`i2v.jsonl`: 12 tasks.** Pass `t2i` outputs into Wan 2.1 I2V 14B (Q4_K_M, 30 steps,
  Flow Match Euler). 4–10 s videos, including 8 s and 10 s chained clips and one
  edit→video pipeline. Benchmark identity preservation, anatomical stability across 81
  frames, and background coherence.

The same set serves as the smoke and regression suite for all model changes.

## 13. Open inputs from the user

- A one-time `cloudflared tunnel login` authorisation in a browser, for `sajiid.me`.
- Sudo on the server (already provided) for the systemd units and the `cloudflared` install.
- BIOS power-on-after-AC-loss setting (manual step at the machine).
- Selection of specific uncensored/realism LoRAs for the FLUX realism strategy.

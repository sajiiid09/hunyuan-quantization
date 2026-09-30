# raco-gen — Self-hosted image & video generation server

**Date:** 2026-09-30
**Status:** Design approved (all six sections), pending spec review
**Host:** `raco-ai-server` (192.168.10.4, Tailscale 100.66.198.27)

## 1. Goal

Run image generation, image editing, text-to-video and image-to-video on `raco-ai-server`,
reachable from anywhere through a fixed API key, for two kinds of clients: ComfyUI on other
PCs and Open WebUI. Generated files belong to the client; the server keeps them for one hour
and then deletes them permanently. HunyuanImage-3.0 is the target image model; it arrives
later through a custom quantization track (section 8), with stopgap models serving until then.

### Out of scope

- 3D generation (Hunyuan3D), audio/Foley, talking avatars.
- 720p video and anything above 10 s.
- Multi-user accounts, billing, per-user keys, a web gallery.
- Hardware changes (the RAM upgrade was considered and rejected).

## 2. Hardware constraints (measured 2026-09-30)

| Item | Value | Consequence |
|---|---|---|
| GPU | RTX 4070 Ti, 12 GB, driver 595.91, CUDA 13 | Models run quantized with offload |
| System RAM | 32 GB (4×8 GB DDR4-3200, all slots used; board max 128 GB) | ~29 GB usable with desktop running; one model group loaded at a time |
| CPU / bus | Ryzen 5 5600G, PCIe 3.0 x16 | ~12 GB/s host→GPU; weight streaming is bus-bound |
| Disk | 512 GB NVMe, 401 GB free on `/` | Enough for all models plus the 169 GB Image3 BF16 download |
| Desktop | GNOME stays running (user decision) | ~2 GB RAM and ~200 MB VRAM reserved for it |
| Existing services | Ports 22, 5432, 7070, 8554, 8888, 8889, 631 | Must not be touched |

HunyuanImage-3.0 public quants do not fit: the smallest (NF4) is ~45 GB against a ~31–34 GB
weight budget (12 GB VRAM + ~29 GB RAM − runtime overhead).

## 3. Architecture

```
 Anywhere                                   raco-ai-server
┌──────────────────┐                      ┌───────────────────────────────────────────┐
│ ComfyUI (any PC) │  HTTPS               │ cloudflared (systemd)                     │
│  + RacoRemote    │──────┐               │     │                                     │
│    nodes         │      │   Cloudflare  │     ▼                                     │
└──────────────────┘      ├──► Tunnel ───►│ Gateway (FastAPI, 127.0.0.1:8100)         │
┌──────────────────┐      │ gen.sajiid.me  │  API key · queue · templates · TTL        │
│ Open WebUI       │──────┘               │     │                    │                │
└──────────────────┘                      │     ▼                    ▼                │
                                          │ ComfyUI (127.0.0.1:8188) Image3 worker    │
                                          │  2.1 / Qwen-Edit / HV1.5  (section 8)     │
                                          └───────────────────────────────────────────┘
```

Units and their single responsibilities:

1. **ComfyUI.** The inference engine for the stopgap image models and all video. It listens
   only on `127.0.0.1:8188`. ComfyUI-Manager is not installed.
2. **Gateway.** The only public-facing process. It checks the API key, validates uploads,
   runs the job queue, fills in workflow templates, serves results and deletes expired
   files. Clients address *tasks*, never model names.
3. **cloudflared.** A new named Cloudflare Tunnel (`raco-gen`) mapping `gen.sajiid.me` to
   `127.0.0.1:8100`. The zone `sajiid.me` is already on Cloudflare nameservers, and `gen` is
   unused as of 2026-09-30. It runs with `--protocol http2`, because this network drops QUIC
   (UDP 7844), as found in `automated-call-centre/scripts/dev.sh`. The desktop only ever
   used quick tunnels, so there is no config to reuse. The server is authorised once with
   `cloudflared tunnel login`. No router ports are opened.
4. **Image3 worker** (added by section 8). A separate Python process with the custom
   weight-streaming loader. The gateway routes image tasks to it once it passes evaluation.
5. **Client adapters.** The `ComfyUI-RacoRemote` node pack and an Open WebUI video tool.

### Always-on behaviour

- ComfyUI, the gateway and cloudflared run as systemd **system** services with `User=raco-ai`,
  `Restart=always`, and are enabled at boot.
- Sleep and suspend are disabled.
- The BIOS "Restore on AC power loss" option is set to *Power On*. This is a manual step for
  the user.
- A UPS is recommended but optional.

## 4. Models and memory

| Task | Model | Quant | Approx. size |
|---|---|---|---|
| `image.generate` | HunyuanImage-2.1 **Distilled** (8 steps), 2K only (2048², 2560×1536, and other 2K buckets) | GGUF Q5_K_M (fallback Q4_K_M) | ~12 GB |
| `image.edit` | Qwen-Image-Edit, newest release on Hugging Face at install time, plus a Lightning LoRA (4–8 steps) | GGUF Q4_K_M | ~13 GB |
| `video.t2v` | HunyuanVideo-1.5 480p T2V CFG-distilled | GGUF Q6_K | ~7 GB |
| `video.i2v`, chain extension | HunyuanVideo-1.5 480p I2V step-distilled (8–12 steps) | GGUF Q6_K | ~7 GB |
| Shared | Qwen2.5-VL-7B text encoder (FP8), ByT5, SigLIP vision encoder, image VAE, video VAE | FP8 / FP16 | ~15 GB |
| Later | HunyuanImage-3.0-Instruct-Distil, custom quant (section 8) | custom | ≤ 30 GB |

Weights come from official Tencent/Qwen repos or established community quantizers
(QuantStack, city96, calcuis). Each file's source URL and SHA-256 go into `models/MANIFEST.md`.
If a single Qwen2.5-VL file works for all three model families it is shared; otherwise the
separate copies are listed in the manifest.

### Memory rules

- **One model group is resident at a time.** Switching groups reloads from NVMe, which costs
  about 10–30 s. The queue groups adjacent jobs of the same task where FIFO fairness allows
  (a job may be passed by at most two jobs).
- Text encoders run first and are offloaded before the main model loads onto the GPU.
- Video decodes with tiled VAE.
- A video segment is **97 frames (~4 s at 24 fps)** by default. The limit rises to 121 frames
  only if the smoke tests show peak VRAM ≤ 11.5 GB with no spill.
- Requests of 6–10 s are **chained**: segment 1 is T2V or I2V, and each later segment is I2V
  started from the previous segment's last frame with the same prompt and seed + n. The
  duplicate joining frame is dropped, and ffmpeg concatenates the segments to H.264 MP4 at
  24 fps without re-timing.

### Expected performance (targets to measure, not promises)

| Job | Target |
|---|---|
| Image generate | 30–60 s |
| Image edit | 30–90 s |
| 4 s 480p clip | a few minutes |
| 10 s chained video | 2–3× a single clip |

## 5. API

Base URL: `https://gen.sajiid.me`. All routes except `GET /v1/health` require authentication.

### Authentication

- The header is `X-API-Key: <key>` or `Authorization: Bearer <key>`.
- There is one fixed 32-hex-character key, generated on the server at install and stored in
  `~/.config/raco-gen/.env` (mode 600) as `RACO_API_KEY`. It changes only when that file is
  edited and the gateway restarted. The example key pasted in chat is not used.
- The comparison is constant-time. A wrong key returns `401`. More than 10 failures per
  minute from one IP (taken from `CF-Connecting-IP`) returns `429` for 10 minutes.

### Asynchronous job API (ComfyUI nodes, video tool)

| Method & path | Purpose |
|---|---|
| `POST /v1/jobs` | Multipart: `task` (`image.generate` \| `image.edit` \| `video.t2v` \| `video.i2v`), `prompt`, optional `negative_prompt`, `aspect` (`1:1`, `16:9`, `9:16`, `4:3`, `3:4`), `seed`, `duration_s` (2–10, video only), `images[]` (1–5 files, ≤ 20 MB each; required for `image.edit` and `video.i2v`). Returns `202 {"job_id": ...}`. |
| `GET /v1/jobs/{id}` | `{status: queued\|running\|done\|failed\|cancelled, queue_position, progress (0–1), error, files: [{name, type, bytes, url, expires_at}]}` |
| `GET /v1/jobs/{id}/files/{name}` | Download a result file |
| `DELETE /v1/jobs/{id}` | Cancel if queued or running; delete its files immediately |
| `GET /v1/health` | Unauthenticated liveness: `{ok, gpu_ok, queue_length, loaded_group}` |

Outputs are PNG for images and MP4 (H.264, yuv420p, 24 fps) for video.

### OpenAI-compatible routes (Open WebUI images)

- `POST /v1/images/generations` maps to `image.generate`.
- `POST /v1/images/edits` maps to `image.edit`.
- The `model` field is accepted and ignored. `size` is mapped to the nearest supported aspect.
- Responses return `b64_json`.
- **Cloudflare's 100 s time-to-response limit.** These routes send `200` headers immediately,
  then a single space every 20 s until the JSON body is ready. If the job fails, the body is
  an OpenAI-style `{"error": ...}` object, still under status 200, because the status line
  has already been sent.

## 6. Data flow and retention

1. An accepted job gets a folder `~/Documents/raco-gen/jobs/<job_id>/`, holding `inputs/` and
   `outputs/`, and a row in `jobs.sqlite` (id, task, params, status, timestamps).
2. The worker fills the task's workflow template, uploads the inputs to ComfyUI, runs the
   graph, and moves the outputs from ComfyUI's `output/` into the job folder.
3. On completion (`done`, `failed` or `cancelled`), `expires_at = finished_at + 60 min`.
4. A sweeper runs every 60 s. It permanently deletes expired job folders, **nulls the prompt
   and params in the database row**, and removes any files older than 60 min in ComfyUI's
   `input/`, `output/` and `temp/` folders.
5. Kept long-term: one log line per job (time, task, duration, status, error code). No
   prompts and no media.
6. After a gateway restart, `queued` jobs resume, `running` jobs are marked `failed:
   interrupted`, and the sweeper runs immediately.

## 7. Limits and error handling

| Condition | Behaviour |
|---|---|
| Queue already holds 20 jobs | `429 queue_full` |
| Upload not decodable as an image by Pillow, or too large | `400 invalid_input` |
| Less than 20 GB free disk | `503 low_disk`; no new jobs accepted |
| Model file missing | `503 model_unavailable` |
| CUDA out of memory | One automatic retry with safer settings (e.g. 73-frame segments, smaller VAE tiles, Q4 fallback for 2.1); then `failed: gpu_oom` |
| Timeout (image 3 min, edit 4 min, video 8 min per segment) | `failed: timeout`; ComfyUI interrupted and VRAM freed |
| ComfyUI down | The gateway restarts it through systemd; jobs wait, and the job fails if ComfyUI is not back within 2 min |

Only one GPU job runs at a time.

## 8. HunyuanImage-3.0 custom quant track (parallel R&D, local only)

**Goal:** HunyuanImage-3.0-Instruct-Distil at **≤ 30 GB**, serving both `image.generate` and
`image.edit` with no client-visible change. **Constraint (user decision):** everything runs
on `raco-ai-server`, with no rented hardware, and untuned quantization comes first.

### Facts that shape the recipe (research 2026-09-30)

- **Structure** (from `config.json` and the modeling code):
  - 32 layers, hidden size 4096.
  - Per layer: 64 routed experts plus 1 `shared_mlp`, top-8 routing, fp32 router `mlp.gate.wg`.
  - Each expert is a separate `HunyuanMLP` with `nn.Linear` layers `gate_and_up_proj`
    (4096→6144, fused) and `down_proj` (3072→4096).
  - Attention is a fused `self_attn.qkv_proj` plus `o_proj`.
  - The routed experts hold ~77B parameters; everything else is ~5.7B.
- **No sub-4-bit build that runs exists.**
  - The lone 31.5 GB `convertor/hyimg3-q2` GGUF has no documentation and nothing can load it.
  - llama.cpp and stable-diffusion.cpp support requests were closed without being built.
- **Intel's AutoRound builds:** MXFP4 experts already shift composition compared with BF16
  (PSNR ≈ 19.5 dB, against 31.6 dB for MXFP8). The loss comes from the experts, not attention.
- **Diffusion models in general:** untuned quantization shows visible damage around 3 bits
  and collapses at 2 bits. Text rendering is the first thing to break.
- **Expert pruning:** REAP keeps quality well at 25% on 128-expert models. On Moonlight,
  which has 64 experts like this model, it kept only 79.8% at 25%. **The cap is 25%.**
- **Calibrated quantization** (AutoRound, GPTQ) needs about 190 GB of RAM plus an 80 GB GPU
  for this model, so it is ruled out by the local-only constraint. HQQ and SDNQ need no
  calibration and can quantize one shard at a time within 32 GB of RAM.
- The EricRollei NF4 build keeps `self_attn`, VAE, vision model, patch/time embeddings and
  `final_layer` in BF16. We follow the same skip list, except attention goes to 8-bit.

### Size budget

- **Non-expert part: ~5.5 GB.** Attention, `shared_mlp`, `wte` and `lm_head` at 8-bit; ViT,
  VAE, router, norms and time embeddings in BF16.
- **Experts: ≤ 24 GB.**

### Stages

0. **References.**
   - Run the 50 text-to-image prompts and the 15 edit tasks in `eval/prompts/` on **Tencent's
     hosted HunyuanImage-3.0**: hunyuan.tencent.com/image for text-to-image, and the
     Hunyuan-Image-3.0-Instruct chat for edits.
   - Tencent Cloud `hy-image-v3` (~$0.03 per image, 0–3 reference images) is the scripted
     alternative.
   - We also use the free Apache-2.0 **T2I-CoReBench-Images** set (1,080 prompts × 4
     HunyuanImage-3.0 base-model images) for scores judged by Qwen2.5-VL.
   - These references anchor quality judgements only. They are not pixel-for-pixel
     references, because the versions and settings differ.
1. **Download** the BF16 Instruct-Distil weights (~169 GB) to `models/image3-bf16/`. They are
   deleted after a candidate is accepted.
2. **Error check per method.** For 2 sample layers, quantize the experts with **HQQ** and with
   **SDNQ (with SVD low-rank correction)** at 2, 3 and 4 bits. Measure the relative output
   error on real activations captured from a single streamed forward pass. Pick the method
   with the lower error at 2–3 bits.
3. **L1, no pruning, untuned (~29 GB).**
   - All 64 experts at ~2.5 bpw average.
   - The first and last 2 layers at 4-bit, the rest a mix of 3-bit and 2-bit: `down_proj` at
     3-bit, `gate_and_up_proj` at 2-bit.
   - Quantized shard by shard from BF16.
4. **Evaluate L1** (see below). If it passes, go to stage 7.
5. **Local profiling pass** for pruning statistics.
   - A custom layer-sequential sweep: load one BF16 layer at a time from NVMe and push
     cached hidden states for a whole batch of prompts through it, one denoising step at a
     time.
   - Batching means each of the 8 steps reads the weights only once: about 8 × 169 GB of
     reads, roughly 2–4 h in total, compute-bound.
   - Prompts: about 256, made up of `eval/prompts`, a T2I-CoReBench subset and edit tasks,
     with a hidden-state cache of about 10 GB on disk.
   - Records REAP saliency per expert: router gate weight × norm of the expert's output.
6. **L2: 25% pruned (64 → 48 experts), 3-bit experts (~28 GB).**
   - Drop the 16 lowest-saliency experts per layer and slice the matching `gate.wg` rows.
     Top-8 routing stays.
   - Quantize the 48 remaining experts at 3-bit, with the first and last 2 layers at 4-bit.
   - Evaluate. If this also fails, the track stops and the decision goes back to the user:
     rent hardware for calibrated AutoRound, upgrade RAM, or stay on the stopgap models.
7. **Runtime (Image3 worker).**
   - Resident on the GPU: all non-expert weights (~5.5 GB) plus activations.
   - Routed experts sit in pinned RAM and are streamed layer by layer on a dedicated CUDA
     stream, prefetching layer n+1 while layer n computes. Dequantize happens on the GPU.
   - Estimate: ~2 s per step bus-bound, so **~20–40 s per image** at 8 steps.
   - `recaption` and `think_recaption` are disabled; token-by-token decoding over PCIe 3.0
     takes minutes.
   - Before an Image3 job, the gateway calls ComfyUI's `/free`.

### Evaluation (every candidate)

- Render `eval/prompts/t2i.jsonl` and `edit.jsonl` with fixed seeds, plus 200 T2I-CoReBench
  prompts.
- Qwen2.5-VL answers each item's `checks` (yes/no). The pass rate is compared against the
  Tencent references and the CoReBench HunyuanImage-3.0 images.
- Also record: text-rendering accuracy (the `text-rendering` category), seconds per image,
  and peak VRAM and RAM.
- The `i2v.jsonl` tasks run on the candidate's outputs, to confirm they animate cleanly with
  HunyuanVideo-1.5.
- A local side-by-side page shows reference and candidate. **Pass = the user approves**, and
  each image takes ≤ 3 min.

**Swap-in:** the winner serves both image tasks. HunyuanImage-2.1 and Qwen-Image-Edit stay
installed as automatic fallbacks.

**Risk:** 2–3 bits without calibration sits right at the known breaking point, and 25%
pruning may hurt a 64-expert model. Neither candidate may pass, in which case the stopgap
models stay in production.

## 9. Clients

### ComfyUI node pack `ComfyUI-RacoRemote`

| Node | Inputs | Outputs |
|---|---|---|
| Raco Generate Image | prompt, aspect, seed | `IMAGE` |
| Raco Edit Image | images 1–5 (`IMAGE`), instruction, seed | `IMAGE` |
| Raco Video | mode (t2v/i2v), start `IMAGE` (optional), prompt, duration_s 2–10, seed | `VIDEO`, `IMAGE` (frames) |

- Each node submits the job, reports queue position and progress to ComfyUI's progress bar,
  downloads the result and returns it. Standard Save nodes then store it on the client PC.
- The URL and key are read from `ComfyUI/user/raco_remote.json`, or from the `RACO_API_URL` /
  `RACO_API_KEY` environment variables. **They are never node settings**, so they cannot leak
  through PNG metadata or shared workflows.
- An interrupt in ComfyUI sends `DELETE /v1/jobs/{id}`.

### Open WebUI

- **Images:** OpenAI image engine, base URL `https://gen.sajiid.me/v1`, the API key, any model
  name. Edits are enabled if the installed Open WebUI version supports OpenAI image edits;
  this is checked during setup.
- **Video:** an Open WebUI Tool `generate_video(prompt, duration_s, use_attached_image)`.
  - It uses the job API and emits status events while it waits.
  - It uploads the MP4 to Open WebUI's file storage and embeds a player in the reply.
  - It requires a chat model that supports tool calling.
- Open WebUI stores results in its own data folder, on its own host.

## 10. Layout, security, updates

```
/home/raco-ai/Documents/raco-gen/
├── comfyui/            # ComfyUI checkout + uv venv (pinned commit)
├── gateway/            # FastAPI app, tests, workflow templates, systemd units
├── image3/             # quant tooling + worker (section 8)
├── clients/
│   ├── comfyui-raco-remote/
│   └── openwebui-video-tool/
├── models/             # all weights + MANIFEST.md
├── jobs/               # per-job folders (1 h TTL) + jobs.sqlite
└── docs/superpowers/specs/
~/.config/raco-gen/.env # RACO_API_KEY, CF tunnel token (mode 600)
```

- **Services run as `raco-ai`.** PyTorch is installed for CUDA 12.8+ via `uv`, compatible
  with driver 595.
- **Custom nodes** are limited to those the templates need (ComfyUI-GGUF, plus whichever
  node supports each model family if native support is missing), each pinned to a commit.
- **Hardening:**
  - no ComfyUI-Manager;
  - ComfyUI and the gateway bind to localhost only;
  - uploads are validated by decoding;
  - wrong-key attempts are throttled;
  - Cloudflare WAF rate limits are optional.
  - No firewall changes, to avoid disturbing existing services.
- **Updates:** `update.sh` pulls the pinned upgrades, re-runs the smoke tests, and rolls back
  on failure.

## 11. Testing

1. **Gateway unit tests (pytest, fake ComfyUI):**
   - key accept/reject and throttling;
   - queue order, grouping bound and the 429;
   - sweeper deletion at 60 min, including prompt nulling;
   - restart recovery;
   - OpenAI response shapes;
   - the whitespace keep-alive surviving a mocked 100 s proxy.
2. **Server smoke tests:**
   - each task end to end, recording time and peak VRAM;
   - a 10 s chained video;
   - a forced OOM retry;
   - a scan confirming no media remains after TTL + 1 min.
3. **External tests** through `gen.sajiid.me` from another network: an image request with a
   wait longer than 100 s, and a video download.
4. **Client tests:**
   - the node pack on the desktop (192.168.10.6; HTTP only, so no GPU is needed);
   - Open WebUI image generation and edit, and the video tool.

## 12. Evaluation set

Stored in the repo under `eval/prompts/`, each item with yes/no `checks` for the Qwen2.5-VL
judge:

- **`t2i.jsonl`: 50 prompts.** Covers counting, spatial layout, attribute binding, text
  rendering, world knowledge, reasoning, negation, product, people, scene, style, infographic,
  long/complex prompts and cultural context. Items 49–50 are image-to-video sources.
- **`edit.jsonl`: 15 tasks.** Instruction edits, restyles, same subject in a new scene,
  multi-reference and layout-keep edits. Their sources are `t2i` outputs.
- **`i2v.jsonl`: 12 tasks.** 4–10 s videos, including 8 s and 10 s chained clips and one
  edit→video pipeline.

The same set serves as the smoke and regression suite for the stopgap models (section 11) and
as the Image3 gate (section 8).

## 13. Open inputs from the user

- A one-time `cloudflared tunnel login` authorisation in a browser, for `sajiid.me`.
- Sudo on the server (already provided) for the systemd units and the `cloudflared` install.
- BIOS power-on-after-AC-loss setting (manual step at the machine).
- A Tencent Hunyuan account (web or Tencent Cloud) to produce the Image3 reference images.

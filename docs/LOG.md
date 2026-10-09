# LOG — performance, bottlenecks, improvements

Append one row per session. Format:

```
| Date | Session focus | Performance measured | Bottlenecks found | Improvements made |
|---|---|---|---|---|
```

Use `—` when a column has no entry. Keep it to one line per session.

| Date | Session focus | Performance measured | Bottlenecks found | Improvements made |
|---|---|---|---|---|
| 2026-10-01 | Phase 0: docs + repo setup | — | — | Root docs written (README, CLAUDE, AGENTS, PLAN, CHANGELOG, LOG); git repo initialized on server and cloned to local |
| 2026-10-01 | Architecture pivot: spec + docs rewrite | — | HunyuanImage-3.0 sub-3-bit quant abandoned (no calibration HW, quality risk) | Pivoted to FLUX.1 [dev] + Wan 2.1 I2V; removed gateway; tunnel → ComfyUI directly; all root docs updated |
| 2026-10-01 | Installation preflight | 400 GiB free; 27 GiB RAM available; GPU 414 MiB idle | Server one documentation commit behind; no implementation; LoRA links pending | Verified SSH and hardware; checking upstream model artifacts before installation |
| 2026-10-05 | Remote audit: Wan 2.1 & ComfyUI status | RTX 4070 Ti idle (454 MiB VRAM used); ComfyUI 0.38.0 live | FLUX/T5 .part SHA mismatch stopped download_models.py; Hunyuan-T2V stalled at 28% | Verified Wan 2.1 I2V 14B (~30.8 GB) 100% complete and recognized by ComfyUI at gen.sajiid.me |
| 2026-10-06 | Generation instructions and live health preflight | Public ComfyUI 0.38.0: queue 0 running / 0 pending; GPU ~452 MiB used, RAM ~25.4 GiB free | Tailscale SSH reauthentication blocks temperatures, power, sensors and logs; FLUX GGUF and T5 absent from live loader lists; local Wan template CFG 1 and missing sampling shift need correction; client generate expects missing node id fields; sync does not convert WEBP | Provided corrected manual workflow guidance (Wan CFG 6, shift 8; FLUX guidance 3.5 / sampler CFG 1) and monitoring commands; no generation or server configuration changes; existing uncommitted files preserved |
| 2026-10-06 | Recover user-created Wan workflow from subgraph blueprint save error | Export inspected: 14 nodes, 17 links; 832x480, 33 frames, CFG 6, shift 8, 20 steps, uni_pc/simple, tiled VAE | Original tab was a subgraph blueprint; prompts blank; one harmless disconnected loader | Copied graph into regular workflow, filled prompts, saved as Wan 2.1 - Image to Video and verified library entry; checked JSON backup in Downloads; no GPU job submitted |
| 2026-10-06 | Live thermal and resource check during user video generation | GPU 70–72 C, 95–97% utilization, ~229–234 W / 285 W, fan 61–62%, VRAM 10102/12282 MiB; CPU 52.9 C, NVMe 40.9 C; RAM 17 GiB available; disk 311 GiB free | ~3.4 GB model offloaded; vmstat 40–41% I/O wait, no active swapping; no active thermal throttling or matching recent kernel errors | Confirmed 1 running / 0 pending jobs and no current thermal concern; previous job completed in 356.63 s; left generation uninterrupted |
| 2026-10-06 | Trace missing video outputs and run a 33-frame Wan I2V test | Found two successful server WebPs (20.7 MB, 21.3 MB); submitted test completed in 322.78 s at 832x480; peak observed GPU temp 74 C, ~100% utilization, ~250 W, fan 64%; returned idle at 45 C; no errors | Prior outputs were only on server, local output folder empty; 12 GB GPU offloaded ~3.2 GB model to CPU | Copied both prior videos and new validated animated WebP to local output; test uses saved image and prompt; queue empty after completion |
| 2026-10-06 | Fix client sync HTTP 403 | Verified direct SSH rsync copied current server outputs; repeat dry-run reported no pending transfers | Cloudflare returns 403 for public `/view`; ComfyUI reused `wani2v_00001_.webp`, so naive skip-existing would preserve stale local content | Sync now uses rsync over SSH, mirrors subfolders, checksum-compares and backs up changed local versions; tested `sync --keep-on-server`; README updated |
| 2026-10-06 | Audit server prompt and input retention | ComfyUI history API currently contains 8 successful job records | Saved workflow contains positive/negative prompts; three source images remain in input; no 24-hour cleanup timer/cron found | Confirmed workflow JSON location, current output files, and that no prompt text was found in recent service journal |

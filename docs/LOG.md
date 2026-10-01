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

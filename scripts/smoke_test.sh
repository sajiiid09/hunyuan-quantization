#!/usr/bin/env bash
# Smoke test: run each workflow end to end, record wall time and peak VRAM.
# VRAM is polled on the server (where the GPU lives) via SSH.
# Usage: bash scripts/smoke_test.sh [output-dir]
cd "$(dirname "$0")/.."

OUT="${1:-$HOME/Documents/raco-gen/output}"
mkdir -p "$OUT"
RESULTS="$OUT/smoke_results.txt"
: > "$RESULTS"
SSH="ssh raco-ai@100.66.198.27"

run() {
  local name="$1"; shift
  echo "=== $name ==="
  local start end out peak
  start=$(date +%s)
  "$SSH" 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 2' \
    > "/tmp/vram_$name.log" 2>/dev/null &
  local vram_pid=$!
  out=$(python3 scripts/client/raco_gen.py generate --output-dir "$OUT" "$@")
  local rc=$?
  end=$(date +%s)
  kill "$vram_pid" 2>/dev/null || true
  wait "$vram_pid" 2>/dev/null || true
  peak=$(sort -n "/tmp/vram_$name.log" 2>/dev/null | tail -1)
  echo "$out"
  if [ "$rc" -eq 0 ]; then
    echo "$name: $((end - start))s, peak ${peak:-?} MiB" | tee -a "$RESULTS"
  else
    echo "$name: FAILED (rc=$rc)" | tee -a "$RESULTS"
  fi
}

run "flux-t2i" --workflow workflows/flux-t2i.json --prompt "a serene mountain lake at sunset, photorealistic"
run "hunyuan-t2v" --workflow workflows/hunyuan-t2v.json --prompt "a red panda climbing a mossy tree, soft daylight"

# Wan i2v uses the FLUX output as its source image
FLUX_IMG=$(ls -t "$OUT"/*flux-t2i*.png 2>/dev/null | head -1 || true)
if [ -n "$FLUX_IMG" ]; then
  run "wan-i2v" --workflow workflows/wan-i2v.json --prompt "smooth camera push-in, cinematic lighting" --image "$FLUX_IMG"
else
  echo "wan-i2v: skipped (no FLUX output found)" | tee -a "$RESULTS"
fi

echo "=== results ==="
cat "$RESULTS"

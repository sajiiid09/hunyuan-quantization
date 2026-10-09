#!/usr/bin/env python3
"""Download model files in parallel range chunks and verify SHA-256.

The Hugging Face CDN throttles each connection to ~0.5-1 MB/s. Downloading each
file in N parallel range chunks multiplies per-file throughput by N.
"""
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verified(path, model):
    if not path.exists() or path.stat().st_size != model['size']:
        return False
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest() == model['sha256']


def download_range(url, chunk_path, start, end):
    subprocess.run(
        ['curl', '--fail', '--location', '--silent', '--show-error',
         '--retry', '5', '--retry-delay', '3', '--connect-timeout', '30',
         '--range', f'{start}-{end}', '--output', str(chunk_path), url],
        check=True,
    )


def download(model, destination, chunks):
    target = destination / model['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if verified(target, model):
        print('VERIFIED', model['id'], flush=True)
        return
    url = (f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}"
           f"/{urllib.parse.quote(model['file'])}")
    size = model['size']
    part_files = [target.parent / f".{target.name}.chunk{i}" for i in range(chunks)]
    for pf in part_files:
        if pf.exists():
            pf.unlink()
    bounds = []
    for i in range(chunks):
        start = i * size // chunks
        end = size - 1 if i == chunks - 1 else (i + 1) * size // chunks - 1
        bounds.append((start, end))
    with concurrent.futures.ThreadPoolExecutor(max_workers=chunks) as pool:
        futs = [pool.submit(download_range, url, pf, s, e)
                for pf, (s, e) in zip(part_files, bounds)]
        for f in futs:
            f.result()
    with open(target, 'wb') as out:
        for pf in part_files:
            with open(pf, 'rb') as inp:
                while True:
                    block = inp.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
            pf.unlink()
    if not verified(target, model):
        raise RuntimeError(f'Size or SHA-256 mismatch: {target}')
    print('COMPLETE', model['id'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'config/models.json')
    parser.add_argument('--destination', type=Path, default=ROOT / 'comfyui/models')
    parser.add_argument('--workers', type=int, default=4, help='concurrent files')
    parser.add_argument('--chunks', type=int, default=8, help='range chunks per file')
    parser.add_argument('--files', default=None, help='only ids containing this substring')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    models = json.loads(args.manifest.read_text())
    if args.files:
        models = [m for m in models if args.files in m['id']]
    args.destination.mkdir(parents=True, exist_ok=True)
    if args.verify_only:
        failures = [m['path'] for m in models if not verified(args.destination / m['path'], m)]
        if failures:
            raise SystemExit('Missing or invalid: ' + ', '.join(failures))
        print(f'All {len(models)} model files verified.')
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda m: download(m, args.destination, args.chunks), models))
    manifest = ROOT / 'models/MANIFEST.md'
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text('# Verified model inventory\n\n' + '\n'.join(
        f"- `{m['path']}` — {m['repo']} @ {m['revision']} — SHA-256 `{m['sha256']}`"
        for m in models) + '\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Download revision-pinned model files and verify their upstream SHA-256."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]


def verified(path, model):
    if not path.exists() or path.stat().st_size != model['size']:
        return False
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() == model['sha256']


def download(model, destination):
    target = destination / model['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if verified(target, model):
        print('VERIFIED', model['id'], flush=True)
        return
    if target.exists():
        raise RuntimeError(f'Existing file failed verification: {target}')
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{urllib.parse.quote(model['file'])}"
    partial = target.with_suffix(target.suffix + '.part')
    print('DOWNLOADING', model['id'], model['size'], flush=True)
    subprocess.run(['curl', '--http1.1', '--fail', '--location', '--silent', '--show-error',
                    '--retry', '8', '--retry-delay', '5', '--connect-timeout', '30',
                    '--speed-limit', '1024', '--speed-time', '120',
                    '--continue-at', '-', '--output', str(partial), url], check=True)
    if not verified(partial, model):
        raise RuntimeError(f'Size or SHA-256 mismatch: {partial}')
    partial.rename(target)
    print('COMPLETE', model['id'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'config/models.json')
    parser.add_argument('--destination', type=Path, default=ROOT / 'comfyui/models')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    models = json.loads(args.manifest.read_text())
    args.destination.mkdir(parents=True, exist_ok=True)
    if args.verify_only:
        failures = [m['path'] for m in models if not verified(args.destination / m['path'], m)]
        if failures:
            raise SystemExit('Missing or invalid: ' + ', '.join(failures))
        print(f'All {len(models)} model files verified.')
        return
    required = sum(m['size'] for m in models if not (args.destination / m['path']).exists())
    if shutil.disk_usage(args.destination).free < required + 10 * 1024**3:
        raise SystemExit('Insufficient disk space, including a 10 GiB reserve.')
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda model: download(model, args.destination), models))
    manifest = ROOT / 'models/MANIFEST.md'
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text('# Verified model inventory\n\n' + '\n'.join(
        f"- `{m['path']}` — {m['repo']} @ {m['revision']} — SHA-256 `{m['sha256']}`"
        for m in models) + '\n')


if __name__ == '__main__':
    main()

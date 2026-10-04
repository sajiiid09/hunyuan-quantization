#!/usr/bin/env python3
"""raco-gen client — generate images/video on the server, keep every output on this machine.

Usage:
  python3 scripts/client/raco_gen.py generate --workflow workflows/flux-t2i.json --prompt "a cat"
  python3 scripts/client/raco_gen.py generate --workflow workflows/wan-i2v.json --prompt "push in" --image photo.png
  python3 scripts/client/raco_gen.py sync

The client submits the workflow to https://gen.sajiid.me, polls for completion,
downloads every output to this machine, and deletes it from the server. Nothing
is left on the server unless --keep-on-server is passed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

API = "https://gen.sajiid.me"
SSH_HOST = "raco-ai@100.66.198.27"
SERVER_OUTPUT = "/home/raco-ai/Documents/raco-gen/comfyui/output"
DEFAULT_OUT = os.path.expanduser("~/Documents/raco-gen/output")


def api(method, path, data=None, raw=False, timeout=60):
    url = API + path
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        content = r.read()
        return content if raw else json.loads(content)


def upload_image(path):
    boundary = uuid.uuid4().hex
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API + "/upload/image", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["name"]


def ssh_run(cmd, timeout=60):
    return subprocess.run(
        ["ssh", SSH_HOST, cmd], capture_output=True, text=True, timeout=timeout
    )


def server_delete(subfolder, filename):
    rel = os.path.join(subfolder, filename) if subfolder else filename
    ssh_run(f"rm -f -- '{SERVER_OUTPUT}/{rel}'")


def convert_webp_to_mp4(webp_path):
    mp4_path = webp_path.rsplit(".", 1)[0] + ".mp4"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", webp_path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-r", "24", mp4_path],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode == 0 and os.path.exists(mp4_path):
        print(f"converted {mp4_path}")
        return mp4_path
    print(f"ffmpeg conversion failed: {r.stderr[:200]}", file=sys.stderr)
    return None


def download_outputs(prompt_id, history, out_dir, keep_on_server):
    os.makedirs(out_dir, exist_ok=True)
    local_files = []
    outputs = history.get(prompt_id, {}).get("outputs", {})
    for node_id, out in outputs.items():
        for key in ("images", "gifs"):
            for f in out.get(key, []):
                fn = f["filename"]
                sf = f.get("subfolder", "")
                tp = f.get("type", "output")
                qs = urllib.parse.urlencode(
                    {"filename": fn, "subfolder": sf, "type": tp}
                )
                data = api("GET", f"/view?{qs}", raw=True, timeout=300)
                local_path = os.path.join(out_dir, f"{prompt_id}_{fn}")
                with open(local_path, "wb") as fh:
                    fh.write(data)
                local_files.append(local_path)
                print(f"saved {local_path} ({len(data) / 1e6:.1f} MB)")
                if not keep_on_server:
                    server_delete(sf, fn)
    return local_files


def cmd_generate(args):
    with open(args.workflow) as f:
        wf = json.load(f)

    clip_nodes = sorted(
        (n for n in wf.values() if n["class_type"] == "CLIPTextEncode"),
        key=lambda n: int(n["id"]),
    )
    if not clip_nodes:
        raise SystemExit("workflow has no CLIPTextEncode node for the prompt")
    clip_nodes[0]["inputs"]["text"] = args.prompt
    if args.negative and len(clip_nodes) > 1:
        clip_nodes[1]["inputs"]["text"] = args.negative

    for n in wf.values():
        if n["class_type"] == "KSampler" and args.seed is not None:
            n["inputs"]["seed"] = args.seed

    if args.image:
        name = upload_image(args.image)
        loaded = False
        for n in wf.values():
            if n["class_type"] == "LoadImage":
                n["inputs"]["image"] = name
                loaded = True
        if not loaded:
            raise SystemExit("workflow has no LoadImage node for --image")

    resp = api("POST", "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    pid = resp["prompt_id"]
    print(f"queued {pid}")

    deadline = time.time() + args.timeout * 60
    history = {}
    while time.time() < deadline:
        try:
            history = api("GET", f"/history/{pid}")
        except urllib.error.HTTPError:
            history = {}
        if pid in history and history[pid].get("outputs"):
            break
        time.sleep(3)
    else:
        raise SystemExit(f"timed out after {args.timeout} min waiting for {pid}")

    status = history.get(pid, {}).get("status", {})
    if status.get("status_str") == "error":
        raise SystemExit(f"job {pid} failed on server: {status.get('errors', [])}")

    local_files = download_outputs(pid, history, args.output_dir, args.keep_on_server)
    for lf in local_files:
        if lf.endswith(".webp"):
            convert_webp_to_mp4(lf)
    print(f"done — {len(local_files)} file(s) on this machine, nothing left on server"
          if not args.keep_on_server else f"done — {len(local_files)} file(s) on this machine")


def cmd_sync(args):
    r = ssh_run(f"find {SERVER_OUTPUT} -type f 2>/dev/null", timeout=120)
    server_files = [f for f in r.stdout.splitlines() if f.strip()]
    if not server_files:
        print("no files on server to sync")
        return
    os.makedirs(args.output_dir, exist_ok=True)
    for sf_path in server_files:
        rel = os.path.relpath(sf_path, SERVER_OUTPUT)
        fn = os.path.basename(rel)
        subfolder = os.path.dirname(rel)
        local_path = os.path.join(args.output_dir, f"sync_{fn}")
        if os.path.exists(local_path):
            print(f"skip {fn} (already local)")
            continue
        qs = urllib.parse.urlencode(
            {"filename": fn, "subfolder": subfolder, "type": "output"}
        )
        data = api("GET", f"/view?{qs}", raw=True, timeout=300)
        with open(local_path, "wb") as fh:
            fh.write(data)
        print(f"synced {local_path} ({len(data) / 1e6:.1f} MB)")
        if not args.keep_on_server:
            server_delete(subfolder, fn)
    print("sync complete")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="run a workflow and keep outputs on this machine")
    g.add_argument("--workflow", required=True)
    g.add_argument("--prompt", required=True)
    g.add_argument("--negative", default=None)
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--image", default=None)
    g.add_argument("--output-dir", default=DEFAULT_OUT)
    g.add_argument("--timeout", type=int, default=30)
    g.add_argument("--keep-on-server", action="store_true")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("sync", help="pull any server-side outputs to this machine")
    s.add_argument("--output-dir", default=DEFAULT_OUT)
    s.add_argument("--keep-on-server", action="store_true")
    s.set_defaults(func=cmd_sync)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

"""Small wrappers around ffmpeg/ffprobe and HTTP, kept in one place so the rest stays testable."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


class ToolMissing(RuntimeError):
    pass


def find(name: str, env_var: str | None = None) -> str | None:
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    return shutil.which(name)


def ffmpeg_bin() -> str:
    b = find("ffmpeg", "SHORTS_FFMPEG")
    if not b:
        raise ToolMissing("ffmpeg is not on PATH. Install it (Windows: winget install Gyan.FFmpeg) or set SHORTS_FFMPEG.")
    return b


def ffprobe_bin() -> str:
    b = find("ffprobe", "SHORTS_FFPROBE")
    if not b:
        raise ToolMissing("ffprobe is not on PATH (it comes with ffmpeg). Or set SHORTS_FFPROBE.")
    return b


def run(args: list[str], *, cwd: Path | None = None, input_text: str | None = None, timeout: float = 900) -> str:
    proc = subprocess.run(args, cwd=cwd, input=input_text, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(args[0]).name} failed ({proc.returncode}): {proc.stderr.strip()[-2000:]}")
    return proc.stdout


def probe(path: Path) -> dict:
    out = run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(out)


def duration(path: Path) -> float:
    info = probe(path)
    d = info.get("format", {}).get("duration")
    if d is None:
        raise RuntimeError(f"could not read the length of {path}")
    return float(d)


def http_json(url: str, payload: dict, headers: dict[str, str], timeout: float = 180) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"{url} answered {e.code}: {body}") from None


def http_bytes(url: str, payload: dict, headers: dict[str, str], timeout: float = 180) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"{url} answered {e.code}: {body}") from None

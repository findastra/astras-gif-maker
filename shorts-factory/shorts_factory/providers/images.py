"""Image providers: one picture per slide.

folder       Your own pictures (Fuzzboi PNGs, VR captures, screenshots). Used in name order, one per slide,
             repeating if there are fewer pictures than slides. A slide's own "image" field always wins.
             No network, no cost. This is the main way to use the tool.
openai       OpenAI Images API (OPENAI_API_KEY; model OPENAI_IMAGE_MODEL, default gpt-image-1, portrait 1024x1536).
placeholder  A locally drawn stand-in (gradient and a fuzzy blob tinted by the slide's hex), for dry runs.
"""

from __future__ import annotations

import base64
import math
import os
import random
from pathlib import Path

from .. import media
from ..presets import Preset
from ..schema import Script

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ppm"}
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"
OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


def list_folder(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise FileNotFoundError(f"image folder not found: {folder}")
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                   key=lambda p: p.name.lower())
    if not files:
        raise FileNotFoundError(f"no pictures ({', '.join(sorted(IMAGE_EXTS))}) in {folder}")
    return files


def assign(script: Script, folder_files: list[Path] | None) -> list[Path | None]:
    """Which picture each slide uses: its own "image" (relative to the script file), else the folder in order."""
    out: list[Path | None] = []
    k = 0
    for s in script.slides:
        if s.image:
            p = Path(s.image)
            if not p.is_absolute() and script.base_dir:
                p = script.base_dir / p
            if not p.is_file():
                raise FileNotFoundError(f"slide picture not found: {p}")
            out.append(p)
        elif folder_files:
            out.append(folder_files[k % len(folder_files)])
            k += 1
        else:
            out.append(None)
    return out


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def placeholder_ppm(path: Path, *, width: int, height: int, top: str, bottom: str, body: str, seed: int) -> Path:
    """Write a binary PPM: vertical gradient, scattered sparkles, and a round fuzzy character with dot eyes."""
    top_c, bot_c, body_c = _hex_rgb(top), _hex_rgb(bottom), _hex_rgb(body)
    buf = bytearray()
    for y in range(height):
        buf += bytes(_mix(top_c, bot_c, y / max(1, height - 1))) * width
    rng = random.Random(seed)

    def fill_row(y: int, x0: int, x1: int, rgb: tuple[int, int, int]):
        x0, x1 = max(0, x0), min(width, x1)
        if 0 <= y < height and x1 > x0:
            buf[(y * width + x0) * 3:(y * width + x1) * 3] = bytes(rgb) * (x1 - x0)

    def disc(cx: int, cy: int, r: int, rgb):
        for dy in range(-r, r + 1):
            half = int((r * r - dy * dy) ** 0.5)
            fill_row(cy + dy, cx - half, cx + half + 1, rgb)

    for _ in range(40):  # sparkles
        sx, sy, sr = rng.randrange(width), rng.randrange(height), rng.choice((1, 2, 2, 3))
        disc(sx, sy, sr, (255, 255, 255))
    cx, cy, r = width // 2 + rng.randint(-width // 10, width // 10), int(height * 0.42), int(width * 0.3)
    disc(cx, cy, r + max(3, width // 90), (0, 0, 0))           # one dark outline
    for k in range(18):                                       # fuzz: little bumps round the edge
        a = 2 * math.pi * k / 18
        disc(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), r // 7, body_c)
    disc(cx, cy, r, body_c)
    ey, ex, er = cy - r // 6, r // 3, max(3, r // 9)
    for sx in (cx - ex, cx + ex):
        disc(sx, ey, er, (0, 0, 0))
        disc(sx - er // 3, ey - er // 3, max(1, er // 3), (255, 255, 255))
    for sx in (cx - int(ex * 1.5), cx + int(ex * 1.5)):       # blush
        disc(sx, ey + er * 2, max(2, er), (255, 140, 190))
    path.write_bytes(f"P6 {width} {height} 255\n".encode() + bytes(buf))
    return path


def make_placeholders(script: Script, preset: Preset, out_dir: Path, slots: list[Path | None], *,
                      width: int = 540, height: int = 960) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result: list[Path] = []
    pal = preset.palette
    for i, (s, have) in enumerate(zip(script.slides, slots)):
        if have:
            result.append(have)
            continue
        body = s.hex or pal[1 + i % (len(pal) - 1)]
        result.append(placeholder_ppm(out_dir / f"slide-{i + 1:02d}.ppm", width=width, height=height, top=pal[0],
                                      bottom=pal[(i + 2) % len(pal)], body=body, seed=i + 1))
    return result


def openai_image(prompt: str, out: Path) -> Path:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set (needed for --images-from openai)")
    model = os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_OPENAI_IMAGE_MODEL)
    data = media.http_json(OPENAI_IMAGES_URL, {"model": model, "prompt": prompt, "size": "1024x1536", "n": 1},
                           {"authorization": f"Bearer {key}"}, timeout=300)
    item = data["data"][0]
    if item.get("b64_json"):
        out.write_bytes(base64.b64decode(item["b64_json"]))
    else:
        raise RuntimeError("the Images API returned no b64_json picture")
    return out


def make_openai(script: Script, preset: Preset, out_dir: Path, slots: list[Path | None]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for i, (s, have) in enumerate(zip(script.slides, slots)):
        if have:
            result.append(have)
            continue
        target = out_dir / f"slide-{i + 1:02d}.png"
        if not target.exists():  # re-runs reuse pictures already paid for
            prompt = f"{s.image_prompt}. Style: {preset.image_style}."
            if s.hex:
                prompt += f" Main colour #{s.hex}."
            openai_image(prompt, target)
        result.append(target)
    return result

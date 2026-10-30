"""The whole run: script -> pictures -> narration -> timing -> captions -> ffmpeg -> checked MP4."""

from __future__ import annotations

import json
import os
import platform
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import captions, ffmpeg_cmd, media, presets, schema, timing
from .providers import images as image_providers
from .providers import script as script_providers
from .providers import tts as tts_providers

IMAGE_SOURCES = ("auto", "folder", "openai", "placeholder")


def data_home() -> Path:
    """Where runs and videos go: outside the code, per PET-PROGRAM-FRAMEWORK.md section 6."""
    if os.environ.get("SHORTS_FACTORY_HOME"):
        return Path(os.environ["SHORTS_FACTORY_HOME"])
    if platform.system() == "Windows" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "astras-pet-os" / "astras-gif-maker" / "shorts-factory"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "short"


@dataclass
class Options:
    topic: str | None = None
    preset: str | None = None
    script_path: Path | None = None
    images_dir: Path | None = None
    images_from: str = "auto"
    tts: str | None = None
    script_provider: str | None = None
    offline: bool = False
    out: Path | None = None
    workdir: Path | None = None
    slides: int = 6
    width: int = 1080
    height: int = 1920
    fps: int = timing.DEFAULT_FPS
    crossfade: float = timing.DEFAULT_CROSSFADE
    transition: str = "fade"
    supersample: float = 2.0
    crf: int = 23
    captions: bool = True
    log: list[str] = field(default_factory=list)


@dataclass
class Result:
    video: Path
    workdir: Path
    script: schema.Script
    plan: timing.Plan
    tts: str
    images_from: str
    probe: dict


def resolve_image_source(opts: Options) -> str:
    src = opts.images_from.lower()
    if src not in IMAGE_SOURCES:
        raise ValueError(f"--images-from must be one of {', '.join(IMAGE_SOURCES)}")
    if src == "auto":
        src = "folder" if opts.images_dir else "placeholder"
    if src == "folder" and not opts.images_dir:
        raise ValueError("--images-from folder needs --images <folder>")
    if opts.offline and src == "openai":
        raise ValueError("offline mode cannot use the OpenAI Images API; use --images <folder> or placeholders")
    return src


def check_video(path: Path, *, width: int, height: int, expect_seconds: float) -> dict:
    info = media.probe(path)
    v = [s for s in info["streams"] if s.get("codec_type") == "video"]
    a = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    problems = []
    if not v:
        problems.append("no video stream")
    elif (v[0].get("width"), v[0].get("height")) != (width, height):
        problems.append(f"video is {v[0].get('width')}x{v[0].get('height')}, expected {width}x{height}")
    if not a:
        problems.append("no audio stream")
    dur = float(info["format"].get("duration", 0))
    if abs(dur - expect_seconds) > 0.25:
        problems.append(f"length is {dur:.2f}s, expected {expect_seconds:.2f}s")
    if problems:
        raise RuntimeError("the rendered video failed its check: " + "; ".join(problems))
    return {"width": v[0]["width"], "height": v[0]["height"], "duration": round(dur, 3),
            "video_codec": v[0].get("codec_name"), "audio_codec": a[0].get("codec_name"),
            "size_bytes": int(info["format"].get("size", 0))}


def run(opts: Options, say=print) -> Result:
    # 1. script
    if opts.script_path:
        script = schema.load(opts.script_path)
        preset = presets.get(opts.preset or script.preset)
        say(f"script: {opts.script_path} ({len(script.slides)} slides)")
    else:
        if opts.offline:
            raise ValueError("offline mode needs --script <file.json>; it never calls a model")
        if not opts.topic:
            raise ValueError("give --topic, or --script with a script JSON")
        preset = presets.get(opts.preset)
        script = script_providers.generate(opts.topic, preset, provider=opts.script_provider, slides=opts.slides)
        say(f"script: written by {script_providers.pick(opts.script_provider)} ({len(script.slides)} slides)")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    work = opts.workdir or (data_home() / "runs" / f"{slugify(script.title)}-{stamp}")
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. pictures
    src = resolve_image_source(opts)
    folder_files = image_providers.list_folder(opts.images_dir) if src == "folder" else None
    slots = image_providers.assign(script, folder_files)
    if src == "openai":
        pics = image_providers.make_openai(script, preset, work / "images", slots)
    else:  # folder (any gaps filled by placeholders) or placeholder
        pics = image_providers.make_placeholders(script, preset, work / "images", slots)
    say(f"pictures: {src} ({len(pics)})")

    # 3. narration
    tts = tts_providers.pick(opts.tts, offline=opts.offline)
    voices = tts_providers.speak_all([s.narration for s in script.slides], work / "voice", tts)
    lengths = [media.duration(p) for p in voices]
    say(f"voice: {tts} ({sum(lengths):.1f}s of narration)")

    # 4. timing and captions
    plan = timing.plan(lengths, crossfade=opts.crossfade, fps=opts.fps)
    cap_file = None
    if opts.captions:
        cues = timing.caption_cues([s.caption_text for s in script.slides], lengths, plan)
        (work / "captions.ass").write_text(captions.build_ass(cues, preset, width=opts.width, height=opts.height),
                                           encoding="utf-8")
        cap_file = "captions.ass"

    # 5. ffmpeg
    motions = [s.motion or preset.motions[i % len(preset.motions)] for i, s in enumerate(script.slides)]
    out = opts.out or (data_home() / "videos" / f"{slugify(script.title)}-{stamp}.mp4")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    render = ffmpeg_cmd.build_command(images=[p.resolve() for p in pics], audios=[p.resolve() for p in voices],
                                      plan=plan, motions=motions, output=out, workdir=work,
                                      captions_file=cap_file, width=opts.width, height=opts.height,
                                      supersample=opts.supersample, transition=opts.transition, crf=opts.crf,
                                      ffmpeg=media.ffmpeg_bin())
    (work / "filter-graph.txt").write_text(render.filter_graph, encoding="utf-8")
    say(f"rendering {plan.total:.1f}s at {opts.width}x{opts.height}...")
    media.run(render.args, cwd=render.cwd, timeout=1800)
    info = check_video(out, width=opts.width, height=opts.height, expect_seconds=plan.total)
    (work / "result.json").write_text(json.dumps({"video": str(out), **info, "tts": tts, "images": src}, indent=2),
                                      encoding="utf-8")
    say(f"done: {out} ({info['duration']}s, {info['size_bytes'] / 1e6:.2f} MB)")
    return Result(video=out, workdir=work, script=script, plan=plan, tts=tts, images_from=src, probe=info)

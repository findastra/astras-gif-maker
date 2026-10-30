"""Command line: python -m shorts_factory <make|script|check|presets> ...  (run from the shorts-factory folder)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import TOOL_LABEL, __version__, media, pipeline, presets, schema
from .providers import script as script_providers
from .providers import tts as tts_providers


def _make(a) -> int:
    opts = pipeline.Options(
        topic=a.topic, preset=a.preset, script_path=Path(a.script) if a.script else None,
        images_dir=Path(a.images) if a.images else None, images_from=a.images_from, tts=a.tts,
        script_provider=a.script_provider, offline=a.offline, out=Path(a.out) if a.out else None,
        workdir=Path(a.work) if a.work else None, slides=a.slides, width=a.width, height=a.height, fps=a.fps,
        crossfade=a.crossfade, transition=a.transition, supersample=a.supersample, crf=a.crf,
        captions=not a.no_captions)
    pipeline.run(opts)
    return 0


def _script(a) -> int:
    preset = presets.get(a.preset)
    s = script_providers.generate(a.topic, preset, provider=a.script_provider, slides=a.slides)
    text = json.dumps(s.to_json(), indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}; edit it, then: python -m shorts_factory make --script {a.out}")
    else:
        print(text)
    return 0


def _validate(a) -> int:
    try:
        s = schema.load(a.file)
    except schema.ScriptError as e:
        print("not valid:")
        for p in e.problems:
            print(f"  - {p}")
        return 1
    print(f"valid: {s.title!r}, {len(s.slides)} slides, preset {s.preset}")
    return 0


def _check(_a) -> int:
    print(f"{TOOL_LABEL}")
    for name, fn in (("ffmpeg", media.ffmpeg_bin), ("ffprobe", media.ffprobe_bin)):
        try:
            print(f"  {name}: {fn()}")
        except media.ToolMissing as e:
            print(f"  {name}: MISSING. {e}")
    have = tts_providers.available()
    print("  speech: " + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in have.items()))
    print(f"  speech auto picks: {tts_providers.pick('auto')}")
    try:
        print(f"  script auto picks: {script_providers.pick('auto')}")
    except RuntimeError:
        print("  script auto picks: none (no ANTHROPIC_API_KEY or OPENAI_API_KEY); --script still works")
    print(f"  output folder: {pipeline.data_home()}")
    return 0


def _presets(_a) -> int:
    for p in presets.PRESETS.values():
        print(f"{p.id:10} {p.name}: {p.tone}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shorts_factory", description=f"Shorts Factory {__version__} ({TOOL_LABEL})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("make", help="make a 1080x1920 MP4")
    m.add_argument("--topic", help="what the video is about (a model writes the script)")
    m.add_argument("--script", help="a script JSON to render instead of asking a model")
    m.add_argument("--preset", choices=list(presets.PRESETS), help="style (default: the script's, else plain)")
    m.add_argument("--images", help="folder of your own pictures, used in name order")
    m.add_argument("--images-from", default="auto", choices=pipeline.IMAGE_SOURCES)
    m.add_argument("--tts", choices=tts_providers.PROVIDERS, help="speech (default auto: offline first)")
    m.add_argument("--script-provider", choices=["auto", *script_providers.CALLERS])
    m.add_argument("--offline", action="store_true", help="dry mode: no network at all (needs --script)")
    m.add_argument("--out", help="output .mp4 (default: the data folder, see `check`)")
    m.add_argument("--work", help="working folder for this run")
    m.add_argument("--slides", type=int, default=6)
    m.add_argument("--width", type=int, default=1080)
    m.add_argument("--height", type=int, default=1920)
    m.add_argument("--fps", type=int, default=30)
    m.add_argument("--crossfade", type=float, default=0.5)
    m.add_argument("--transition", default="fade")
    m.add_argument("--supersample", type=float, default=2.0, help="smoother motion, slower render (1 to 2)")
    m.add_argument("--crf", type=int, default=23, help="quality: lower is better and bigger (18-28)")
    m.add_argument("--no-captions", action="store_true")
    m.set_defaults(fn=_make)

    s = sub.add_parser("script", help="only write the script JSON, to read and edit before rendering")
    s.add_argument("--topic", required=True)
    s.add_argument("--preset", default="plain", choices=list(presets.PRESETS))
    s.add_argument("--script-provider", choices=["auto", *script_providers.CALLERS])
    s.add_argument("--slides", type=int, default=6)
    s.add_argument("--out")
    s.set_defaults(fn=_script)

    v = sub.add_parser("validate", help="check a script JSON")
    v.add_argument("file")
    v.set_defaults(fn=_validate)

    sub.add_parser("check", help="what is installed and which providers auto would pick").set_defaults(fn=_check)
    sub.add_parser("presets", help="list style presets").set_defaults(fn=_presets)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (ValueError, RuntimeError, FileNotFoundError, KeyError, media.ToolMissing) as e:
        print(f"shorts_factory: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

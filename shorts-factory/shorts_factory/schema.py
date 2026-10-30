"""The script format: a topic turned into 5 to 8 slides.

A script is plain JSON so Astra can write or edit one by hand and render it with no AI at all:

    {
      "schema": "shorts-factory-script-v1",
      "title": "Meet the Fuzzbois",
      "topic": "what a Fuzzboi is",
      "preset": "fuzzbois",
      "slides": [
        {"narration": "This is a Fuzzboi.", "image_prompt": "a fuzzy hand-drawn character",
         "image": "art/fuzzboi-01.png", "caption": "meet the fuzzbois", "motion": "zoom-in",
         "hex": "ff3ec8"}
      ]
    }

Only ``slides[].narration`` and ``slides[].image_prompt`` are required per slide. ``image`` (a path,
relative to the script file), ``caption`` (on-screen text if it should differ from the narration),
``motion`` and ``hex`` (a Fuzzboi's 6-digit look code, also used to tint placeholder art) are optional.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_ID = "shorts-factory-script-v1"
MIN_SLIDES = 5
MAX_SLIDES = 8
MAX_NARRATION_CHARS = 320
MAX_PROMPT_CHARS = 1000
MOTIONS = ("zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down", "still")
HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


class ScriptError(ValueError):
    """The script JSON does not follow shorts-factory-script-v1. ``problems`` lists every issue."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass
class Slide:
    narration: str
    image_prompt: str
    image: str | None = None
    caption: str | None = None
    motion: str | None = None
    hex: str | None = None

    @property
    def caption_text(self) -> str:
        return self.caption if self.caption else self.narration


@dataclass
class Script:
    title: str
    slides: list[Slide]
    topic: str = ""
    preset: str = "plain"
    base_dir: Path | None = field(default=None, compare=False)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"schema": SCHEMA_ID, "title": self.title, "topic": self.topic,
                               "preset": self.preset, "slides": []}
        for s in self.slides:
            d = {"narration": s.narration, "image_prompt": s.image_prompt}
            for k in ("image", "caption", "motion", "hex"):
                v = getattr(s, k)
                if v:
                    d[k] = v
            out["slides"].append(d)
        return out


def _str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate(data: Any, *, min_slides: int = MIN_SLIDES, max_slides: int = MAX_SLIDES) -> list[str]:
    """Return every problem with ``data`` (empty list when it is a valid script)."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["the script must be a JSON object"]
    schema = data.get("schema", SCHEMA_ID)
    if schema != SCHEMA_ID:
        problems.append(f"schema must be {SCHEMA_ID!r}, not {schema!r}")
    if not _str(data.get("title")):
        problems.append("title is required (a short string)")
    for k in ("topic", "preset"):
        if k in data and not isinstance(data[k], str):
            problems.append(f"{k} must be a string")
    slides = data.get("slides")
    if not isinstance(slides, list):
        problems.append("slides must be a list")
        return problems
    if not (min_slides <= len(slides) <= max_slides):
        problems.append(f"slides must hold {min_slides} to {max_slides} slides, not {len(slides)}")
    for i, s in enumerate(slides, 1):
        where = f"slide {i}"
        if not isinstance(s, dict):
            problems.append(f"{where} must be an object")
            continue
        if not _str(s.get("narration")):
            problems.append(f"{where}: narration is required")
        elif len(s["narration"]) > MAX_NARRATION_CHARS:
            problems.append(f"{where}: narration is {len(s['narration'])} characters (at most {MAX_NARRATION_CHARS})")
        if not _str(s.get("image_prompt")):
            problems.append(f"{where}: image_prompt is required")
        elif len(s["image_prompt"]) > MAX_PROMPT_CHARS:
            problems.append(f"{where}: image_prompt is longer than {MAX_PROMPT_CHARS} characters")
        for k in ("image", "caption"):
            if k in s and s[k] is not None and not _str(s[k]):
                problems.append(f"{where}: {k} must be a non-empty string when given")
        if s.get("motion") is not None and s.get("motion") not in MOTIONS:
            problems.append(f"{where}: motion must be one of {', '.join(MOTIONS)}")
        if s.get("hex") is not None and not (isinstance(s["hex"], str) and HEX_RE.match(s["hex"])):
            problems.append(f"{where}: hex must be a 6-digit hex code like ff3ec8")
        unknown = set(s) - {"narration", "image_prompt", "image", "caption", "motion", "hex"}
        if unknown:
            problems.append(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
    return problems


def parse(data: Any, *, base_dir: Path | None = None, **limits: int) -> Script:
    problems = validate(data, **limits)
    if problems:
        raise ScriptError(problems)
    slides = [Slide(narration=s["narration"].strip(), image_prompt=s["image_prompt"].strip(),
                    image=s.get("image"), caption=(s.get("caption") or None), motion=s.get("motion"),
                    hex=(s["hex"].lstrip("#").lower() if s.get("hex") else None))
              for s in data["slides"]]
    return Script(title=data["title"].strip(), slides=slides, topic=data.get("topic", ""),
                  preset=data.get("preset", "plain") or "plain", base_dir=base_dir)


def load(path: str | Path, **limits: int) -> Script:
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    return parse(data, base_dir=p.resolve().parent, **limits)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Pull the JSON object out of a model's reply (tolerates code fences and leading prose)."""
    t = _FENCE.sub("", text.strip())
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise ScriptError(["the reply held no JSON object"]) from None
        try:
            return json.loads(t[start:end + 1])
        except json.JSONDecodeError as e:
            raise ScriptError([f"the reply's JSON did not parse: {e}"]) from None

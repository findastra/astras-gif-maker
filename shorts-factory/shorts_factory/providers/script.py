"""Script providers: topic + preset -> a validated shorts-factory-script-v1.

anthropic  Anthropic Messages API. Needs ANTHROPIC_API_KEY (an API key with a spend limit, never the Max plan).
           Model: ANTHROPIC_MODEL (default below).
openai     OpenAI Chat Completions. Needs OPENAI_API_KEY. Model: OPENAI_MODEL.
file       A script JSON you wrote or edited (--script). No network.
"""

from __future__ import annotations

import json
import os

from .. import media, schema
from ..presets import Preset

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def build_prompt(topic: str, preset: Preset, slides: int = 6) -> tuple[str, str]:
    """System and user prompts. Pure, so it is tested."""
    slides = max(schema.MIN_SLIDES, min(schema.MAX_SLIDES, slides))
    rules = "\n".join(f"- {r}" for r in preset.rules)
    system = (
        "You write scripts for 30 to 45 second vertical videos (TikTok, Reels, Shorts). "
        "Reply with one JSON object and nothing else.\n"
        f"Audience: {preset.audience}.\nTone: {preset.tone}.\n"
        + (f"Rules:\n{rules}\n" if rules else "")
        + "The JSON follows this shape exactly:\n"
        + json.dumps({"schema": schema.SCHEMA_ID, "title": "short title", "topic": "the topic",
                      "preset": preset.id,
                      "slides": [{"narration": "one or two short spoken sentences",
                                  "image_prompt": "what the picture shows",
                                  "caption": "optional shorter on-screen text"}]})
        + f"\nWrite {slides} slides (allowed: {schema.MIN_SLIDES} to {schema.MAX_SLIDES}). Each narration is at most "
          f"25 words and {schema.MAX_NARRATION_CHARS} characters. Slide 1 hooks the viewer in under 3 seconds. "
          f"Image prompts describe one clear subject; the style is added for you, so do not repeat it. "
          f"Optional per-slide fields: caption, motion (one of {', '.join(schema.MOTIONS)}), hex (6-digit code)."
    )
    user = f"Topic: {topic}"
    return system, user


def _anthropic(system: str, messages: list[dict]) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    data = media.http_json(ANTHROPIC_URL, {"model": model, "max_tokens": 2000, "system": system,
                                           "messages": messages},
                           {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _openai(system: str, messages: list[dict]) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    data = media.http_json(OPENAI_URL, {"model": model, "response_format": {"type": "json_object"},
                                        "messages": [{"role": "system", "content": system}, *messages]},
                           {"authorization": f"Bearer {key}"})
    return data["choices"][0]["message"]["content"]


CALLERS = {"anthropic": _anthropic, "openai": _openai}


def pick(name: str | None) -> str:
    """auto -> anthropic when ANTHROPIC_API_KEY is set, else openai when OPENAI_API_KEY is set."""
    name = (name or os.environ.get("SHORTS_SCRIPT") or "auto").lower()
    if name != "auto":
        if name not in CALLERS:
            raise ValueError(f"script provider must be auto, {', '.join(CALLERS)}")
        return name
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError("No script provider: set ANTHROPIC_API_KEY or OPENAI_API_KEY, or pass --script with a "
                       "script JSON you wrote (see examples/).")


def generate(topic: str, preset: Preset, *, provider: str | None = None, slides: int = 6, call=None) -> schema.Script:
    """Ask the model for a script; on a schema error, ask once more with the problems listed."""
    name = pick(provider) if call is None else "custom"
    call = call or CALLERS[name]
    system, user = build_prompt(topic, preset, slides)
    messages = [{"role": "user", "content": user}]
    last_err: schema.ScriptError | None = None
    for _ in range(2):
        reply = call(system, messages)
        try:
            data = schema.extract_json(reply)
            if isinstance(data, dict):
                data.setdefault("schema", schema.SCHEMA_ID)
                data.setdefault("preset", preset.id)
                data.setdefault("topic", topic)
            return schema.parse(data)
        except schema.ScriptError as e:
            last_err = e
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "That JSON has problems: " + "; ".join(e.problems)
                          + ". Reply with the corrected JSON object only."}]
    assert last_err is not None
    raise last_err

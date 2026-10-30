"""Timing math: how long each slide shows, where the crossfades sit, and when each caption appears.

With N slides of visual length d[i] and a crossfade of X seconds between neighbours, slide i+1 starts
X seconds before slide i ends, so

    start[i]  = d[0] + ... + d[i-1] - i*X
    offset[i] = start[i+1] = d[0] + ... + d[i] - (i+1)*X     (the xfade offset after slide i)
    total     = sum(d) - (N-1)*X

Narration for slide i plays from start[i] for ``audio_slot[i]`` seconds: d[i] - X for every slide but the
last (the next slide's narration starts when the fade into it starts) and d[i] for the last, so the
audio track is exactly as long as the picture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_FPS = 30
DEFAULT_CROSSFADE = 0.5
DEFAULT_LEAD_IN = 0.25   # silence before narration starts on each slide
DEFAULT_TAIL = 0.45      # silence after narration before the fade
DEFAULT_MIN_SLIDE = 2.5
WORDS_PER_SECOND = 2.6   # speaking rate used to estimate length when there is no audio yet


@dataclass(frozen=True)
class Plan:
    durations: list[float]       # visual length of each slide (s)
    starts: list[float]          # when each slide starts on the final timeline (s)
    xfade_offsets: list[float]   # offset for each xfade (len N-1)
    audio_slots: list[float]     # length each slide's narration is padded to (s)
    total: float
    crossfade: float
    fps: int

    def frames(self, i: int) -> int:
        return frames_for(self.durations[i], self.fps)


def frames_for(seconds: float, fps: int) -> int:
    return max(1, round(seconds * fps))


def snap(seconds: float, fps: int) -> float:
    """Round a time to a whole number of frames, so ffmpeg's trims and offsets line up exactly."""
    return frames_for(seconds, fps) / fps


def estimate_speech_seconds(text: str) -> float:
    words = len(re.findall(r"\S+", text))
    return max(0.8, words / WORDS_PER_SECOND)


def slide_duration(audio_seconds: float, *, crossfade: float = DEFAULT_CROSSFADE, lead_in: float = DEFAULT_LEAD_IN,
                   tail: float = DEFAULT_TAIL, min_slide: float = DEFAULT_MIN_SLIDE, is_last: bool = False,
                   fps: int = DEFAULT_FPS) -> float:
    """Visual length for one slide so its narration fits before the next fade begins."""
    if audio_seconds < 0:
        raise ValueError("audio length cannot be negative")
    need = lead_in + audio_seconds + tail + (0.0 if is_last else crossfade)
    return snap(max(min_slide, need, 2 * crossfade + 1.0 / fps), fps)


def plan(audio_seconds: list[float], *, crossfade: float = DEFAULT_CROSSFADE, fps: int = DEFAULT_FPS,
         lead_in: float = DEFAULT_LEAD_IN, tail: float = DEFAULT_TAIL, min_slide: float = DEFAULT_MIN_SLIDE) -> Plan:
    if not audio_seconds:
        raise ValueError("at least one slide is needed")
    if crossfade < 0:
        raise ValueError("crossfade cannot be negative")
    n = len(audio_seconds)
    x = snap(crossfade, fps) if crossfade > 0 else 0.0
    if n == 1:
        x = 0.0
    durations = [slide_duration(a, crossfade=x, lead_in=lead_in, tail=tail, min_slide=min_slide,
                                is_last=(i == n - 1), fps=fps) for i, a in enumerate(audio_seconds)]
    starts, t = [], 0.0
    for i, d in enumerate(durations):
        starts.append(round(t, 6))
        t += d - (x if i < n - 1 else 0.0)
    offsets = [starts[i + 1] for i in range(n - 1)]
    slots = [round(d - x, 6) if i < n - 1 else d for i, d in enumerate(durations)]
    total = round(sum(durations) - (n - 1) * x, 6)
    return Plan(durations=durations, starts=starts, xfade_offsets=offsets, audio_slots=slots, total=total,
                crossfade=x, fps=fps)


_DANGLING = {"a", "an", "the", "of", "to", "and", "or", "is", "=", "in", "on", "for", "with", "my", "your", "its",
             "it's", "from", "at", "by", "&", "+"}


def chunk_words(text: str, max_words: int = 4, max_chars: int = 26) -> list[str]:
    """Split a caption into short TikTok-style chunks, breaking early after sentence punctuation."""
    words = re.findall(r"\S+", text)
    chunks: list[str] = []
    cur: list[str] = []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            # don't leave a dangling "a", "the", "=" at the end of a chunk: carry it into the next one
            carry: list[str] = []
            while len(cur) > 1 and len(carry) < 2 and cur[-1].lower() in _DANGLING:
                carry.insert(0, cur.pop())
            chunks.append(" ".join(cur))
            cur = carry
        cur.append(w)
        if re.search(r"[.!?;:,]$", w) and len(cur) >= 2:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def caption_cues(captions: list[str], audio_seconds: list[float], p: Plan, *, lead_in: float = DEFAULT_LEAD_IN,
                 max_words: int = 4) -> list[Cue]:
    """Timed caption chunks. Each slide's chunks share its narration time in proportion to their length."""
    cues: list[Cue] = []
    for i, text in enumerate(captions):
        chunks = chunk_words(text, max_words=max_words)
        if not chunks:
            continue
        speak = max(audio_seconds[i], 0.6 * len(chunks))
        t0 = p.starts[i] + lead_in
        # never run past the moment the next slide's fade starts
        hard_end = p.starts[i] + (p.durations[i] - p.crossfade if i < len(captions) - 1 else p.durations[i])
        speak = min(speak, max(0.1, hard_end - t0))
        weights = [len(c) + 3 for c in chunks]
        total_w = sum(weights)
        t = t0
        for c, w in zip(chunks, weights):
            dt = speak * w / total_w
            cues.append(Cue(round(t, 3), round(t + dt, 3), c))
            t += dt
    return cues

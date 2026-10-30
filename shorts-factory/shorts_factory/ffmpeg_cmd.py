"""Builds the single ffmpeg command that turns slide pictures and narration into the finished vertical MP4.

Per slide: cover-scale the picture to the frame (supersampled so slow motion does not shimmer), then Ken Burns
motion with ``zoompan``. Slides are joined with ``xfade`` crossfades, the narration clips are padded to their
slots and concatenated, and the captions (an ASS file) are burned in last.

The command refers to the captions file by a bare file name, so it must run with ``cwd`` set to the folder
that holds it (``Render.cwd``). That avoids quoting Windows drive letters inside a filter graph.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from .timing import Plan

ZOOM = 0.15  # how far Ken Burns zooms or how much room a pan has (15%)

TRANSITIONS = ("fade", "fadeblack", "fadewhite", "slideleft", "slideup", "circleopen", "dissolve", "smoothleft")


def motion_expr(motion: str, frames: int, zoom: float = ZOOM) -> tuple[str, str, str]:
    """zoompan's z, x and y expressions for one slide. ``on`` is the output frame number."""
    last = max(1, frames - 1)
    p = f"(on/{last})"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    hi = f"{1 + zoom:.4f}"
    if motion == "zoom-in":
        return f"1+{zoom}*{p}", cx, cy
    if motion == "zoom-out":
        return f"{hi}-{zoom}*{p}", cx, cy
    if motion == "pan-right":
        return hi, f"(iw-iw/zoom)*{p}", cy
    if motion == "pan-left":
        return hi, f"(iw-iw/zoom)*(1-{p})", cy
    if motion == "pan-down":
        return hi, cx, f"(ih-ih/zoom)*{p}"
    if motion == "pan-up":
        return hi, cx, f"(ih-ih/zoom)*(1-{p})"
    if motion == "still":
        return "1", "0", "0"
    raise ValueError(f"unknown motion {motion!r}")


def even(n: float) -> int:
    v = int(math.ceil(n))
    return v + (v % 2)


@dataclass(frozen=True)
class Render:
    args: list[str]
    filter_graph: str
    cwd: Path


def build_command(*, images: list[Path], audios: list[Path], plan: Plan, motions: list[str], output: Path,
                  workdir: Path, captions_file: str | None = "captions.ass", width: int = 1080, height: int = 1920,
                  supersample: float = 2.0, transition: str = "fade", crf: int = 23, preset: str = "veryfast",
                  ffmpeg: str = "ffmpeg", audio_rate: int = 48000) -> Render:
    n = len(images)
    if not (n == len(audios) == len(motions) == len(plan.durations)):
        raise ValueError("images, audios, motions and the plan must all have one entry per slide")
    if n == 0:
        raise ValueError("no slides")
    if transition not in TRANSITIONS:
        raise ValueError(f"transition must be one of {', '.join(TRANSITIONS)}")
    if width % 2 or height % 2:
        raise ValueError("width and height must be even for H.264")
    fps = plan.fps
    sw, sh = even(width * supersample), even(height * supersample)

    args = [ffmpeg, "-hide_banner", "-y", "-loglevel", "error"]
    for img in images:
        args += ["-i", str(img)]
    for aud in audios:
        args += ["-i", str(aud)]

    parts: list[str] = []
    for i in range(n):
        frames = plan.frames(i)
        z, x, y = motion_expr(motions[i], frames)
        parts.append(
            f"[{i}:v]trim=end_frame=1,setpts=PTS-STARTPTS,"
            f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,crop={sw}:{sh},setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps},"
            f"trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p,settb=AVTB[v{i}]"
        )
    last = "v0"
    for i, off in enumerate(plan.xfade_offsets):
        out = f"x{i + 1}"
        parts.append(f"[{last}][v{i + 1}]xfade=transition={transition}:duration={plan.crossfade:.4f}:"
                     f"offset={off:.4f}[{out}]")
        last = out
    tail = "format=yuv420p"
    if captions_file:
        tail = f"subtitles={captions_file},format=yuv420p"
    parts.append(f"[{last}]{tail}[vout]")

    for i in range(n):
        slot = plan.audio_slots[i]
        parts.append(f"[{n + i}:a]aresample={audio_rate},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     f"apad=whole_dur={slot:.4f},atrim=0:{slot:.4f},asetpts=PTS-STARTPTS[a{i}]")
    parts.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]")
    graph = ";\n".join(parts)

    args += ["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
             "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps),
             "-c:a", "aac", "-b:a", "128k", "-ar", str(audio_rate),
             "-t", f"{plan.total:.4f}", "-movflags", "+faststart", str(output)]
    return Render(args=args, filter_graph=graph, cwd=workdir)

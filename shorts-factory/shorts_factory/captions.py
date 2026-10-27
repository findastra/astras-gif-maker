"""Burned-in captions as an ASS subtitle file (rendered by ffmpeg's ``subtitles`` filter through libass)."""

from __future__ import annotations

from .presets import Preset
from .timing import Cue


def ass_time(seconds: float) -> str:
    """ASS timestamps are H:MM:SS.cc (centiseconds)."""
    cs = max(0, round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_color(rrggbb: str, alpha: int = 0) -> str:
    """ASS colours are &HAABBGGRR."""
    h = rrggbb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def escape_text(text: str) -> str:
    # Braces start override blocks and a backslash starts a tag; newlines become \N.
    return (text.replace("\\", "⧵").replace("{", "(").replace("}", ")")
            .replace("\r", "").replace("\n", "\\N"))


def build_ass(cues: list[Cue], preset: Preset, *, width: int, height: int, uppercase: bool = True) -> str:
    scale = height / 1920
    size = max(10, round(preset.caption_size * scale))
    outline = max(1, round(7 * scale))
    shadow = max(0, round(3 * scale))
    margin_v = round(preset.caption_margin_v * scale)
    margin_h = round(70 * scale)
    lines = [
        "[Script Info]",
        "; Written by Shorts Factory (Astra's GIF Maker)",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Cap,{preset.caption_font},{size},{ass_color(preset.caption_color)},{ass_color(preset.caption_color)},"
        f"{ass_color(preset.caption_outline)},{ass_color('000000', 0x80)},-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,"
        f"{margin_h},{margin_h},{margin_v},1",
        f"Style: Hi,{preset.caption_font},{size},{ass_color(preset.caption_highlight)},"
        f"{ass_color(preset.caption_highlight)},{ass_color(preset.caption_outline)},{ass_color('000000', 0x80)},-1,0,0,0,"
        f"100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for i, c in enumerate(cues):
        style = "Hi" if i % 2 else "Cap"
        text = escape_text(c.text.upper() if uppercase else c.text)
        # a quick pop-in: start at 85% and settle at 100% over 120 ms
        pop = r"{\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"
        lines.append(f"Dialogue: 0,{ass_time(c.start)},{ass_time(c.end)},{style},,0,0,0,,{pop}{text}")
    return "\n".join(lines) + "\n"

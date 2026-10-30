"""Style presets: how the script sounds, what the pictures ask for, and how captions look."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    audience: str
    tone: str
    image_style: str
    caption_font: str = "Arial"
    caption_size: int = 84            # at 1080x1920; scaled for smaller renders
    caption_color: str = "ffffff"     # RRGGBB
    caption_outline: str = "000000"
    caption_highlight: str = "ffe94d"  # every other chunk, for rhythm
    caption_margin_v: int = 420       # from the bottom; clears TikTok's own buttons and text
    palette: tuple[str, ...] = ("0a0714", "9b7bff", "ff3ec8", "5ffbf1")
    motions: tuple[str, ...] = ("zoom-in", "pan-right", "zoom-out", "pan-up", "pan-left")
    rules: tuple[str, ...] = field(default_factory=tuple)


PRESETS: dict[str, Preset] = {
    "fuzzbois": Preset(
        id="fuzzbois",
        name="Fuzzbois TikTok",
        audience="TikTok viewers who like cute collectible characters and indie NFT art",
        tone="playful, warm, a little chaotic; short punchy lines; first slide is a hook",
        image_style=("hand-drawn fuzzy cartoon character, thick black outline, bright flat neon colours, "
                     "plain soft background, centred, vertical 9:16 composition"),
        caption_font="Arial Black",
        caption_color="ffffff",
        caption_outline="1a0026",
        caption_highlight="5ffbf1",
        palette=("1a0026", "ff3ec8", "5ffbf1", "ffe94d"),
        rules=("Fuzzbois are Astra's own hand-drawn characters; each one's look is set by a 6-digit hex code.",
               "When a slide shows a specific Fuzzboi, put its hex code in the slide's \"hex\" field.",
               "Never promise prices, profits or investment returns."),
    ),
    "mommys": Preset(
        id="mommys",
        name="Mommy's promo",
        audience="VRChat players who might join a dance academy and entertainers club",
        tone="hype, welcoming, confident; invites people to come dance; last slide is a call to action",
        image_style=("VRChat nightclub stage, dancers mid-pose, neon pink and violet lights, haze, "
                     "vertical 9:16 composition"),
        caption_font="Arial Black",
        caption_color="ffffff",
        caption_outline="2b0030",
        caption_highlight="ff8ad8",
        palette=("12001a", "ff3ec8", "9b7bff", "ff8ad8"),
        rules=("Mommy's is a VRChat dance academy and entertainers club.",
               "Do not invent event dates, times, prices or links; say 'link in bio' for where to join."),
    ),
    "vr-clips": Preset(
        id="vr-clips",
        name="VR clip",
        audience="VR and VRChat fans",
        tone="first person, curious, immersive; describes what it feels like to be there",
        image_style="first-person view inside a VRChat world, neon lighting, wide angle, vertical 9:16 composition",
        caption_font="Arial",
        caption_highlight="5ffbf1",
        palette=("050d1a", "1f6feb", "5ffbf1", "c0f803"),
        motions=("zoom-in", "pan-left", "pan-right", "zoom-out"),
    ),
    "plain": Preset(
        id="plain",
        name="Plain explainer",
        audience="a general audience",
        tone="clear, friendly, factual",
        image_style="clean illustration, simple shapes, soft colours, vertical 9:16 composition",
    ),
}


def get(preset_id: str | None) -> Preset:
    key = (preset_id or "plain").strip().lower()
    if key not in PRESETS:
        raise KeyError(f"unknown preset {preset_id!r}; choose one of: {', '.join(PRESETS)}")
    return PRESETS[key]

# Shorts Factory: a vertical video tool of Astra's GIF Maker

Astra asked for "the Cung List" (2026-10-26), item 9: a pipeline in the shape of Tyson Cung's `shortfactory-kids`
(MIT; topic → script → per-slide images → TTS → ffmpeg), mapped onto her own projects as a tool of Gif Giraffe,
for Fuzzbois TikToks, Mommy's promos and VR clips. The reference repo could not be read from this session, so this
is written from scratch to that shape; no code was copied from it.

## What changed

- `shorts-factory/` — the tool `astras-gif-maker-v0.1.0-shorts-factory-v0.1.0`, Python standard library plus
  ffmpeg: topic + style preset → script of 5 to 8 slides (`shorts-factory-script-v1`) → one picture per slide →
  narration per slide → one ffmpeg command → 1080×1920 H.264/AAC MP4 with burned-in captions (ASS), Ken Burns
  motion (`zoompan`) and crossfades (`xfade`), checked with ffprobe after rendering.
  - Providers chosen by flag or environment: script by Anthropic API, OpenAI or a hand-written JSON; pictures from
    her own folder (first-class), OpenAI Images or local placeholders; voice by Windows SAPI, Piper, espeak-ng,
    silent or OpenAI. `auto` is offline first; `--offline` refuses every network provider.
  - Presets: `fuzzbois`, `mommys`, `vr-clips`, `plain`. A slide's `hex` carries a Fuzzboi's look code.
  - `run-shorts-factory-20261026.ps1` checks for Python and ffmpeg (installs them with winget only with
    `-Install`) and runs it; `-Sample` renders the offline example.
  - 37 tests: script schema, timing math, caption timing, the ffmpeg command builder, provider choice, and two
    small real renders when ffmpeg is present.
- `docs/shorts-factory-how-to-20261026.html` — the how-to.
- `index.html` — the tool panel `gif-giraffe-shorts-factory-tool-panel`: its paired lights, one line and an
  **Open how-to** button. The lights are saved in the browser only.
- `pet.json` — a `tools` entry for it. `README.md` — how to run it and its limits. `AGENTS.md`, `CLAUDE.md` —
  changes are recorded here now (hub card 069), plus a short Shorts Factory section. `.gitignore` — videos, audio
  and caches.

## Not done

- Not run on Windows: SAPI voice, Piper and the PowerShell script are untested; so are the paid providers (no
  keys here). Default model names were not checked against the live APIs.
- The hub does not list the tool yet: `system-map.json` (a `tool` node of `gif-maker`) and the registry table in
  `TOOLS-AND-TRICKS.md` need a hub pull request.

Claude Opus 5.5 (`claude-opus-5-5`), 2026-10-26. Public credit: Astra.

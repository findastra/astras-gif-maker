# Gif Giraffe

*By Astra.*

Gif Giraffe is a placeholder for a pet app that will make GIFs. Nothing works yet. Its pixel twin and nine mood frames are in `art/frames/gif-giraffe/`, and `https://raw.githubusercontent.com/findastra/astras-pet-os/main/art/app-icons/astras-gif-maker/icon.png` is the idle frame.

## How to run it

Open `index.html` in a browser. It shows a placeholder page only.

## Limits

- No GIF making yet.
- Status is **growing** (art done, no working app yet).

Desktop appearance draft updated 2026-10-11: see [desktop details](https://raw.githubusercontent.com/findastra/astras-pet-os/main/desktop-art/gif-giraffe/desktop-pet-20261011.json). This changes the desktop pet, not application features.

## Shorts Factory (a tool of Astra's GIF Maker)

`shorts-factory/` turns a topic, or a script you wrote, into a 1080×1920 vertical MP4 for TikTok, Reels or Shorts:
a script of 5 to 8 slides, one picture per slide, narration per slide, burned-in captions, slow Ken Burns motion and
crossfades. Made for Fuzzbois TikToks, Mommy's promos and VR clips. Full how-to: [docs/shorts-factory-how-to-20261026.html](docs/shorts-factory-how-to-20261026.html).

### How to run it

Needs Python 3.10+ and ffmpeg. On Windows, from `shorts-factory\`:

```powershell
.\run-shorts-factory-20261026.ps1 -Install check   # installs only what is missing (winget), then lists providers
.\run-shorts-factory-20261026.ps1 -Sample          # free offline sample, opens the video
.\run-shorts-factory-20261026.ps1 make --offline --script .\my.json --images "$HOME\Pictures\Fuzzbois"
```

Anywhere else: `cd shorts-factory && python -m shorts_factory make --offline --script examples/fuzzbois-dry-run.json`.

| Stage | Free, offline | Paid (only when chosen) |
|---|---|---|
| Script | a script JSON you write (`--script`) | Anthropic API (`ANTHROPIC_API_KEY`) or OpenAI (`OPENAI_API_KEY`) |
| Pictures | your own folder (`--images`), or placeholders | OpenAI Images (`--images-from openai`) |
| Voice | Windows voices (sapi), Piper, espeak-ng, or silent | OpenAI speech (`--tts openai`) |

`--offline` refuses every network provider. Keys are read from environment variables only. Videos go to
`%LOCALAPPDATA%\astras-pet-os\astras-gif-maker\shorts-factory\videos\` unless `--out` says otherwise.

Tests: `cd shorts-factory && python -m unittest discover -s tests` (37 tests; two render real videos when ffmpeg is installed).

### Limits

- Run and checked on Linux only (espeak-ng voice, placeholder and folder pictures). The Windows voice, Piper, the
  PowerShell script and the paid providers have not been run yet.
- Default model names are not checked against the live APIs; set `ANTHROPIC_MODEL`, `OPENAI_MODEL`,
  `OPENAI_IMAGE_MODEL` or `OPENAI_TTS_MODEL` if one is refused.
- Pictures only (no video clips as input), no background music.

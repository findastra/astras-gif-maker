# AGENTS.md

This is **Gif Giraffe**, a pet app in Astra's PetOS. It is a placeholder.

- Read `pet.json` and `PET-FILES` rules in `astras-pet-os` before changing anything.
- Keep `pet.json`, `sprite.json` and `index.html` real files; the hub checks them.
- Changes are recorded in this repo's `changes/` folder, one file per change (`changes/<topic>-YYYYMMDD.md`), never as a new line here (Astra, 2026-10-21, hub card 069).
- First built with: Claude Haiku 5.5 (claude-haiku-5-5), 2026-10-09.

## Shorts Factory (a tool, `shorts-factory/`)

Python (standard library only) plus ffmpeg. Run its tests with `python -m unittest discover -s tests` from `shorts-factory/` (or `pytest` there). Keys come only from environment variables; never commit one, a `.env` file or a rendered video. Anthropic calls need an API key with a spend limit, never Astra's Max plan. How to use it: `docs/shorts-factory-how-to-20261026.html`.

# Astra's GIF Maker becomes a native program, with its own tool panel

Astra, 2026-10-22: "Make sure the gif maker can be its own panel on the Giff Giraffe".

A GIF maker needs a screen of its own (a frame list to reorder, a live preview, a palette, export),
so by PET-PROGRAM-FRAMEWORK.md section 3 it is too big for a tool panel: it becomes **its own website,
a native program this pet program manages**, and the pet program page keeps one tool panel that shows
how it is doing and opens it.

## In this repo

- `astras-gif-maker-20261022.html` — the native program: the working GIF maker. Frames, seamless
  blend across the loop, a pastel-rainbow sparkle overlay inset from the edges, randomize, download
  or a Discord webhook. Everything runs in the browser; no frame leaves the page.
- `index.html` — the entry stays a real file and now opens the native program instead of saying
  nothing works.
- `pet.json` — `job`, `status: growing`, `version: 0.1.0`, `framework`, an `intelligence_levels`
  block with the native program at L1, and `hub.submit` so the Farmer's next round picks the job up.
- `README.md` — what it does, how to run it, and the limits, including that nobody has built a GIF
  with it in a browser yet.

The tool panel itself is in the hub (`scripts/pet-program-pages-20261018.mjs`, `PET_PANELS`), because
the pet program page is generated there.

## Not done

- Never run in a browser end to end: the frame-sequencing arithmetic and the page's script were
  checked on their own, nothing more.
- No L2 runtime and no L3 seat.
- Gif Giraffe still needs a job from Astra: what kind of GIFs should it make?

Claude Opus 5 (`claude-opus-5`), 2026-10-22.

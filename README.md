# Astra's Gif Maker

*By Astra.*

Gif Giraffe looks after **Astra's GIF Maker**, a GIF maker that runs entirely in your browser. Frames you add never leave the page: there is no upload and no server.

Its pixel twin and nine mood frames are in the hub at `art/frames/gif-giraffe/`, and `https://raw.githubusercontent.com/findastra/astras-pet-os/main/art/app-icons/astras-gif-maker/icon.png` is the idle frame.

## How to run it

Open `index.html` in a browser and press **Open Astra's GIF Maker**, or open `astras-gif-maker-20261022.html` directly.

## What Astra's GIF Maker does

- **Frames** — drop in or pick images, reorder them, remove them.
- **Seamless blend** — crossfades between frames, including the loop back to the first, so playback is smooth instead of jumpy.
- **Sparkles** — a starfield overlay: fine coloured dust and bright four-point glints with diffraction spikes. Every star is inset from the edge by its own radius, so none is cut off.
- **Pastel rainbow palette** — twelve swatches in spectrum order, six to a row.
- **Randomize** — one press shuffles delay, blend and sparkle settings.
- **Export** — download the GIF, or send it to a Discord channel with a webhook URL you paste in.

Frames are drawn to *cover* the canvas rather than fit inside it, so there is no letterbox border around images that are not square.

GIF encoding uses [gif.js](https://github.com/jnordberg/gif.js) from a CDN. It tries background workers first; if that script is blocked or stalls, it falls back to encoding on the main thread after 6 seconds instead of hanging.

## Limits

- **Not tested in a browser yet.** The frame-sequencing arithmetic and the page's script were checked on their own; nobody has built a GIF with it end to end.
- The Discord webhook is typed in each time and is never saved.
- Status is **growing**.
- Gif Giraffe has no runtime (L2) and no seat (L3): nothing runs on its own.

Desktop appearance draft updated 2026-10-11: see [desktop details](https://raw.githubusercontent.com/findastra/astras-pet-os/main/desktop-art/gif-giraffe/desktop-pet-20261011.json). This changes the desktop pet, not application features.

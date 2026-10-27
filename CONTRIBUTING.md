# Contributing to Capri

Capri is open source and we want help, choom. Whether you code, draw, or just break things and tell us about it,
there's room for you.

## Ways to help

- **Art.** Her nap sprite (`assets/desk/nap.png`, a small transparent PNG) is wide open, and so are original
  replacement sprites (see the license note below).
- **Brain.** Better prompts, smarter memory, new abilities (`capri/brain/`, `capri/abilities/`).
- **Desktop life.** New effects, moves and reactions (`capri/desk/`).
- **Voice.** A real voice for her, as long as it runs locally and fast.
- **Ports.** She's Windows-only right now (window ledges, OCR, media keys). macOS / Linux help is welcome.
- **Bugs.** Open an issue with what you did, what she did, and the end of `data/capri.log`.

## Getting started

1. Fork the repo and clone it.
2. Run `start.bat` (Python 3.10–3.12; any GPU with 4-8 GB VRAM). The setup window downloads her models.
3. Her log is `data\capri.log` (brain: `data\llama-server.log`, ears: `data\whisper-server.log`).
4. Tests run without a model or GPU: `.venv\Scripts\python -m pytest tests`.

## Pull requests

- Keep each PR to one thing, and say what it changes and how you tested it.
- Match the style around you: small functions, plain names, comments that say *why*.
- Don't commit models, `data/`, `config.yaml` or recordings (they're gitignored).

## A note on the art

The code is MIT. The sprites in `assets/desk/sprites` are by
[lachydotmcg](https://github.com/lachydotmcg/capri-desktop) under PolyForm Noncommercial, so this project (and your
fork) must stay non-commercial while it uses them. Original sprites contributed under a permissive license are very
welcome: they'd let Capri drop that restriction.

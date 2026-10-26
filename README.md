<p align="center">
  <img src="docs/images/dropin.gif" width="210" alt="Capri drops in from the top of the screen">
  <img src="docs/images/talking.png" width="210" alt="Capri talking in her speech bubble">
  <img src="docs/images/defrag.gif" width="210" alt="Capri defrags into her own pixels and rebuilds on a window">
</p>

<h1 align="center">Capri</h1>

<p align="center">
  <b>Capri from <i>Cyberpunk: Edgerunners 2</i>, living on your Windows desktop.</b><br>
  A local AI desktop companion: she sits on your windows, talks back, remembers you, DJs your music and judges your taste.<br>
  100% local. No API keys, no cloud, no subscription.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#what-she-does">What she does</a> ·
  <a href="#contributing">Contributing</a> ·
  <a href="LICENSE">MIT license</a>
</p>

---

## What she does

- **Lives on your desktop.** She drops in from the top of the screen, stands on the taskbar, sits on your window
  title bars and icons, and rides along when you drag a window. Close it and she falls.
- **Defrags.** Every so often she breaks into her own pixels, they stream across the screen, and she rebuilds
  somewhere else.
- **Toss her around.** Grab her, throw her, and she lands in a splash of her own pixels.
- **Talks back.** Hold **Ctrl+1** and talk, or click her and type. A local 12B brain (Mistral-Nemo) answers in her
  voice, with Night City slang and lore, streamed into her speech bubble in under a second.
- **Remembers you.** She picks up facts from normal chat (your cat's name, your games, what you hate) and uses them later.
- **Sees what you're doing.** Ask "what am I doing?" and she reads the window you're in (Windows OCR, nothing saved,
  logins / banking / private windows are always skipped). Now and then she reacts, and checks in when you go quiet.
- **Music.** "Play Nightcall", "change the music", "skip", "pause". She opens YouTube for you, and her hair glitches
  to the beat of whatever's playing.
- **DJ mode.** Turn on *Let her DJ* and she roasts your song and swaps in a Cyberpunk 2077 / Edgerunners OST.
- **Video mode.** `run.bat video` plays a script and records it, with a 9:16 TikTok cut that follows her around.

<p align="center">
  <img src="docs/images/perched.png" width="260" alt="Capri sitting on a Capri CMD window">
  <img src="docs/images/patch_notes.png" width="260" alt="Capri patch notes">
</p>

## Install

**You need:** Windows 10/11 (64-bit), [Python 3.10–3.12](https://www.python.org/downloads/), and an NVIDIA GPU with
**8 GB+ VRAM** (12 GB recommended). About **10 GB** of free disk space.

```bat
git clone https://github.com/Capri-cmd/capri-ai.git
cd capri-ai
setup.bat
```

`setup.bat` makes its own Python environment in `.venv`, installs everything (including the CUDA libraries, so no
CUDA toolkit needed), and downloads her models:

| | Model | Size |
| --- | --- | --- |
| Brain | [Mistral-Nemo-Instruct-2407, IQ4_XS GGUF](https://huggingface.co/bartowski/Mistral-Nemo-Instruct-2407-GGUF) | 6.7 GB |
| Ears | [faster-whisper small.en](https://huggingface.co/Systran/faster-whisper-small.en) | 0.5 GB |

Already have a GGUF? `setup.bat --model-path D:\path\to\model.gguf` uses it instead of downloading.

Then start her:

```bat
run.bat
```

Her first start takes a minute while the brain loads. Set your name in `config.yaml` (`user_name`) so she knows what
to call you.

## Using her

| Do this | She does |
| --- | --- |
| Hold **Ctrl+1** and talk | Hears you and answers. Rebind the key, switch to **Auto** (always listening) or pick your mic under right-click > **Ears** |
| Click her | Opens her type box |
| Drag her, let go mid-swing | Throws her |
| Double-click | Defrags somewhere new |
| Right-click | Jack in (talk), Defrag, Go dormant (nap), Breach the sky (drop in again), DJ / Vibe / Eyes / Chatter toggles, Delta (quit) |
| Tray icon click | Nap / wake |
| "play Nightcall", "change the music", "skip", "pause" | Music, through YouTube (or Spotify with API keys in `config.yaml`) |
| "open Discord", "open Brave" | Opens apps and sites |
| "remember that I main Jett" | Saves it (she also learns on her own) |

Everything is in `config.yaml`; her menu remembers your toggles in `data/settings.json`.

## Video mode

`run.bat video` plays `video.txt` top to bottom and records it. When the console says **READY**, press **F9**. It
hides the taskbar, records the desktop, rebuilds the sound exactly, and saves `videos/capri_<time>.mp4` plus a
`_tiktok.mp4` 9:16 cut. Script steps: `drop`, `say: ...`, `wait: 1.5`, `cmd`, `defrag`, `chip`, `wake: 0.7`.

## How it works

```
capri/
  desk/       her on the desktop: capri.py (states, physics, defrag), fx.py (effects), bubble.py (speech bubble),
              ledges.py (windows / icons / taskbar to sit on), sfx.py (synthesized sounds), video.py, app.py (wiring)
  brain/      persona.py (her character), agent.py (reply loop, memory, anti-repeat), intents.py (music / apps), llm.py
  abilities/  memory, launcher (apps + YouTube), vision (window + OCR), music (OST playlist + beat detection), spotify
  voice/      stt.py (mic + faster-whisper), hotkey.py (hold-to-talk keys)
```

- **Brain:** llama.cpp with the whole prompt cached, so only new words get read. Replies stream sentence by sentence.
- **Anti-repeat:** her recent openers get pushed down in the model, and a first sentence that repeats an old line is
  thrown away and rewritten before you see it.
- **Sounds:** every effect and her talking blips are synthesized in code; no sample files.

## Contributing

**We want contributors!** Artists, coders, testers: see [CONTRIBUTING.md](CONTRIBUTING.md). Good first things:

- Draw her nap sprite (`assets/desk/nap.png`).
- Original sprites under a permissive license, so Capri can drop the non-commercial restriction.
- A local voice for her.
- macOS / Linux support.

Run the tests (no GPU needed): `.venv\Scripts\python -m pytest tests`

## Credits & license

- Code: [MIT](LICENSE).
- Sprites: [lachydotmcg/capri-desktop](https://github.com/lachydotmcg/capri-desktop), PolyForm Noncommercial
  (`assets/desk/LICENSE.md`). Because of them, Capri is **non-commercial** for now.
- Font: Share Tech Mono, SIL Open Font License.
- Capri and Cyberpunk: Edgerunners belong to CD PROJEKT RED / Studio Trigger. Unofficial fan project, not affiliated
  with or endorsed by them.

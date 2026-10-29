"""Makes Capri-Dev-Test: the dev version's source and nothing else, as a folder + zip to hand to other devs.
Only the files on the list below go in. No stream / TikTok / video code, no ERU AI bridge, no torch eyes, and never
data\\ (memory, settings, chat logs). Ends with a scan for anything personal. Run: python tools/make_dev_test.py [out]"""
import re
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC / "build" / "Capri-Test"

# all of her code, minus what this build leaves out: TikTok stream mode, the scripted video, the ERU AI bridge
SKIP = {"capri/__main__.py", "capri/eru_bridge.py", "capri/desk/stream.py", "capri/desk/term.py", "capri/desk/video.py"}
FILES = ["capri_dev.py"] + sorted(
    p.relative_to(SRC).as_posix() for p in (SRC / "capri").rglob("*.py")
    if "__pycache__" not in p.parts and "live" not in p.parts and p.relative_to(SRC).as_posix() not in SKIP)
DIRS = ["assets"]
RENAME = {"portable/config.yaml": "config.yaml"}

RUN_BAT = (SRC / "start.bat").read_text(encoding="utf-8").replace("portable\\requirements.txt", "requirements.txt")
RUN_BAT = RUN_BAT.replace("start.bat", "run.bat")
RUN_SH = (SRC / "run.sh").read_text(encoding="utf-8").replace("portable/requirements.txt", "requirements.txt")
REQS = (SRC / "portable" / "requirements.txt").read_text(encoding="utf-8").replace("pytest\n", "")
README = """# Capri, dev build (source)

Capri from *Cyberpunk: Edgerunners 2*, living on your desktop. This is the test build: her desktop self,
chat, ears, memory and the Brain menu for trying models. Windows 10/11 or Linux, Python 3.10+, a GPU with 4-8 GB VRAM.

## Run

**Windows:** double-click **run.bat**. **Arch / CachyOS:** `bash run.sh` in a terminal.

The first time it makes a `.venv` and installs the packages in `requirements.txt` (no torch, no CUDA toolkit).
Then setup asks you, right there in the terminal (y/n, Enter takes the default):

- **Your name** - what she calls you
- **Brain** - yes/no, then which: Nemotron Heretic E4B (recommended, can see your screen), Mistral-Nemo 12B,
  Conversational 7B, CapriAI2 (Qwen3.5 4B), or a .gguf already on your PC. No = she runs without AI.
- **Engine** - CUDA if you have an NVIDIA card (you can say no), else Vulkan
- **Ears** - talk to her with your mic: whisper.cpp tiny / base / small / medium
- **Voice** - she talks out loud in her cloned voice (the model is in `models/voice/capri-clone`; setup gets
  the 390 MB of helper files Genie-TTS needs to run it on the CPU) or uses talking blips
- **Eyes** - she can look at your screen when you ask
- **Arch only** - offers to `sudo pacman -S` what she needs (python, portaudio, xcb-util-cursor, vulkan-icd-loader,
  whisper-cpp for her ears, tesseract + spectacle for her eyes, playerctl for music)

It shows the total size and free space, then downloads with a progress bar. Downloads resume if they drop (Ctrl+C
pauses). Everything lands inside this folder (`models/`, `engines/`). Run setup again any time:
`run.bat --setup` / `bash run.sh --setup`.

## Linux notes

- On Wayland (KDE Plasma's default) she runs through XWayland, because Wayland doesn't let apps move their own
  windows and she walks by moving hers. She roams the bottom of the screen fine, but she can only stand on top of
  X11 / XWayland windows. A Plasma (X11) session gives the full thing.
- The hold-to-talk key reads the keyboard from `/dev/input`, which needs your user in the `input` group:
  `sudo usermod -aG input $USER`, then log out and back in. Without it the key only works on X11 while one of her
  windows has focus. Typing to her always works.
- "Watch my screen" uses Spectacle (KDE) on Wayland or a plain X11 grab, then tesseract.

## What she can do for you

Ask in plain words, typed or spoken:

- **Search the net** - "search up the best netrunner cyberware", "what's the weather in Tokyo". Real web results need a
  free Brave Search API key (https://brave.com/search/api/) or a SearXNG URL in `config.yaml` under `search:`;
  without one she uses Wikipedia + DuckDuckGo instant answers (good for facts and lore, not news or prices).
- **Read a page** - "summarize https://..."
- **Write text files** - "make me a txt with a packing list": saved in Documents/Capri and opened.
- **Draft emails** - "write an email to sam@example.com saying I'll be late": your mail app opens with it filled in.
  She never sends anything; you do.
- **Open apps and sites, play music, remember things** - as before.
- **MCP tools** - plug in any MCP server under `mcp: servers:` in `config.yaml` (example in
  `capri/abilities/mcp.py`). Read-only tools run right away; tools that change things ask you first.

## Testing your own model

Put any `.gguf` in `models\\llm`, right-click her > **Brain**, pick it. It swaps live, no restart. Anything llama.cpp
release b11932 runs works; thinking is switched off and the chat template comes from the GGUF.

## How she talks to the model

`capri/brain/persona.py` is her character sheet, examples and reminder. `capri/brain/agent.py` builds each prompt:
character sheet as the first user turn, her acknowledgement, the examples, the last 12 exchanges, then your message
with notes in [brackets] and the reminder. `capri/brain/llm.py` (`LlamaServerLLM`) runs llama-server and streams
replies.

## Files

    capri_dev.py        entry point (setup window, then her)      run.bat / run.sh   start her
    capri/              her code          assets/   sprites, font, icons
    config.yaml         settings (your name, context size, temperature...)
    models/  engines/   created by setup          data/     her settings, memory and logs (created on first run)

Logs for bug reports: `data\\capri.log`, `data\\llama-server.log`, `data\\whisper-server.log`.

Fan-made. Capri and Cyberpunk: Edgerunners belong to CD PROJEKT RED. Not for redistribution.
"""

PRIVATE = re.compile(r"wahibe|@gmail|hiburavt|onedrive|\\users\\|saturnx|capri-cmd|@users\.noreply|"
                     r"[A-Za-z]:\\\\?(?:users|capri|eru)", re.I)

if OUT.exists():
    shutil.rmtree(OUT)
for rel in FILES:
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / rel, dst)
for d in DIRS:
    shutil.copytree(SRC / d, OUT / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "face", "video"))
for a, b in RENAME.items():
    shutil.copy2(SRC / a, OUT / b)
# her cloned voice model ships with her (setup downloads only the helper files Genie needs)
shutil.copytree(SRC / "models" / "voice" / "capri-clone", OUT / "models" / "voice" / "capri-clone")
(OUT / "run.bat").write_text(RUN_BAT.replace("\n", "\r\n"), encoding="utf-8")
(OUT / "run.sh").write_bytes(RUN_SH.replace("\r\n", "\n").encode("utf-8"))
(OUT / "requirements.txt").write_text(REQS, encoding="utf-8")
(OUT / "README.md").write_text(README, encoding="utf-8")

hits = []
for p in OUT.rglob("*"):
    if p.is_file() and p.suffix in (".py", ".bat", ".sh", ".md", ".txt", ".yaml"):
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if PRIVATE.search(line):
                hits.append(f"{p.relative_to(OUT)}:{i}: {line.strip()[:120]}")
print("\n".join(hits) if hits else "personal-info scan: clean")
zip_path = shutil.make_archive(str(OUT), "zip", OUT.parent, OUT.name)
import tarfile


def _exec(info):  # run.sh stays executable on Linux
    if info.name.endswith(".sh"):
        info.mode = 0o755
    return info


tar_path = str(OUT) + "-arch.tar.gz"
with tarfile.open(tar_path, "w:gz") as tf:
    tf.add(OUT, arcname=OUT.name, filter=_exec)
print("wrote", OUT, ",", zip_path, "and", tar_path)

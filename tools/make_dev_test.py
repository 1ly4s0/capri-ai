"""Makes Capri-Dev-Test: the dev version's source and nothing else, as a folder + zip to hand to other devs.
Only the files on the list below go in. No stream / TikTok / video code, no ERU AI bridge, no torch eyes, and never
data\\ (memory, settings, chat logs). Ends with a scan for anything personal. Run: python tools/make_dev_test.py [out]"""
import re
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\CapriBuild\Capri-Dev-Test")

FILES = [
    "capri_dev.py", "build_dev.bat",
    "capri/__init__.py", "capri/config.py", "capri/portable.py", "capri/setup.py",
    "capri/brain/__init__.py", "capri/brain/agent.py", "capri/brain/intents.py", "capri/brain/llm.py",
    "capri/brain/persona.py",
    "capri/abilities/__init__.py", "capri/abilities/memory.py", "capri/abilities/launcher.py",
    "capri/abilities/spotify.py", "capri/abilities/music.py", "capri/abilities/vision.py",
    "capri/voice/__init__.py", "capri/voice/stt.py", "capri/voice/hotkey.py", "capri/voice/tts.py",
    "capri/desk/__init__.py", "capri/desk/app.py", "capri/desk/bubble.py", "capri/desk/capri.py", "capri/desk/fx.py",
    "capri/desk/ledges.py", "capri/desk/mini.py", "capri/desk/settings.py", "capri/desk/sfx.py",
    "capri/desk/sprites.py",
]
DIRS = ["assets"]
RENAME = {"portable/config.yaml": "config.yaml"}

RUN_BAT = (SRC / "start.bat").read_text(encoding="utf-8").replace("portable\\requirements.txt", "requirements.txt")
RUN_BAT = RUN_BAT.replace("start.bat", "run.bat")
REQS = (SRC / "portable" / "requirements.txt").read_text(encoding="utf-8").replace("pytest\n", "")
README = """# Capri, dev build (source)

Capri from *Cyberpunk: Edgerunners 2*, living on your Windows desktop. This is the test build: her desktop self,
chat, ears, memory and the Brain menu for trying models. Windows 10/11, Python 3.10-3.12, a GPU with 4-8 GB VRAM.

## Run

Double-click **run.bat** (`run.bat --setup` opens the setup window again). The first time it makes a `.venv` and installs the packages in `requirements.txt` (no
torch, no CUDA toolkit). Then a setup window asks what to download and shows the total size:

- **Brain** - Mistral-Nemo 12B, Conversational 7B and/or CapriAI2 (Qwen3.5 4B)
- **Ears** - whisper.cpp tiny / base / small / medium, or none (type only)
- **Brain engine** - llama.cpp, Vulkan (any GPU) or CUDA (NVIDIA)

Downloads resume if they drop. Everything lands inside this folder (`models\\`, `engines\\`); nothing is installed
system-wide.

## Testing your own model

Put any `.gguf` in `models\\llm`, right-click her > **Brain**, pick it. It swaps live, no restart. Anything llama.cpp
release b11932 runs works; thinking is switched off and the chat template comes from the GGUF.

## How she talks to the model

`capri/brain/persona.py` is her character sheet, examples and reminder. `capri/brain/agent.py` builds each prompt:
character sheet as the first user turn, her acknowledgement, the examples, the last 12 exchanges, then your message
with notes in [brackets] and the reminder. `capri/brain/llm.py` (`LlamaServerLLM`) runs llama-server and streams
replies.

## Files

    capri_dev.py        entry point (setup window, then her)
    capri/              her code          assets/   sprites, font, icons
    config.yaml         settings (your name, context size, temperature...)
    build_dev.bat       optional: builds a Capri.exe with PyInstaller
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
    shutil.copytree(SRC / d, OUT / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "face"))
for a, b in RENAME.items():
    shutil.copy2(SRC / a, OUT / b)
(OUT / "run.bat").write_text(RUN_BAT.replace("\n", "\r\n"), encoding="utf-8")
(OUT / "requirements.txt").write_text(REQS, encoding="utf-8")
(OUT / "README.md").write_text(README, encoding="utf-8")
bat = (OUT / "build_dev.bat").read_text(encoding="utf-8")
bat = bat.replace(r'set "B=D:\CapriBuild"', r'set "B=%~dp0build"').replace("D:\\CapriBuild\\", "build\\")
(OUT / "build_dev.bat").write_text(bat, encoding="utf-8")

hits = []
for p in OUT.rglob("*"):
    if p.is_file() and p.suffix in (".py", ".bat", ".md", ".txt", ".yaml"):
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if PRIVATE.search(line):
                hits.append(f"{p.relative_to(OUT)}:{i}: {line.strip()[:120]}")
print("\n".join(hits) if hits else "personal-info scan: clean")
zip_path = shutil.make_archive(str(OUT), "zip", OUT.parent, OUT.name)
print("wrote", OUT, "and", zip_path)

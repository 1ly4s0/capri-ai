"""Config loading. Defaults live here; config.yaml in the repo root overrides them."""
from __future__ import annotations

import copy
import os
from pathlib import Path

try:
    import yaml
except ImportError:  # yaml is optional, defaults still work
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
MODELS = ROOT / "models"

# the brain setup.bat downloads (bartowski's GGUF of Mistral-Nemo-Instruct-2407, 12B, ~6.7 GB)
MODEL_REPO = "bartowski/Mistral-Nemo-Instruct-2407-GGUF"
MODEL_FILE = "Mistral-Nemo-Instruct-2407-IQ4_XS.gguf"

DEFAULTS: dict = {
    "user_name": "choom",  # what Capri calls you
    # how she lives on the desktop
    "desk": {
        "size": 240,  # her height in pixels
        "video_size": 360,  # her height in video mode (big enough for a 9:16 phone crop)
        "roam_seconds": [18, 40],  # she defrags somewhere new every this-many seconds
        "intro": True,  # the drop-in from the top of the screen on launch
        # these four are first-run defaults; after that her right-click menu remembers your choice
        "dj": False,  # let her swap your YouTube music for Cyberpunk OSTs when she thinks it's not nova
        "vibe": True,  # her hair glitches to the beat of whatever's playing
        "eyes": True,  # she glances at the window you're in (title + Windows OCR, nothing saved)
        "chatter": True,  # she pipes up when you've been quiet a while, and reacts to what you open
        "chatter_idle_minutes": 6,  # no keyboard / mouse this long: she says something
        "react_cooldown_minutes": 4,  # at most one unprompted remark per this many minutes
    },
    "stt": {
        "mode": "hold",  # hold = hold the talk key while you speak; auto = she listens all the time; off
        "talk_key": "ctrl+1",
        "input_device": "",  # part of the mic's name; "" = Windows default (also pickable in her menu)
        "model": "small.en",  # faster-whisper model, downloaded into models/whisper by setup.bat
        "hotwords": "Capri, Campy, Capricorn, choom, chooms, preem, nova",
        "silence_seconds": 0.7,  # auto mode: this much quiet ends a sentence
        "energy_threshold": 0.015,
    },
    "llm": {
        # llama_cpp: load a GGUF directly; openai: any OpenAI-compatible server (LM Studio, Ollama, llama-server, ...)
        "backend": "llama_cpp",
        "model_path": "",  # empty = models/ + MODEL_FILE (what setup.bat downloads); or point at any GGUF you have
        "n_ctx": 5120,  # her prompt is ~2.4k tokens plus ~1.4k of chat history and the reply; 8-bit cache keeps it small
        "n_gpu_layers": -1,  # -1 = all on the GPU; she steps down by herself if it doesn't fit
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "not-needed",
        "model": "local-model",
        "temperature": 0.7,
        "max_tokens": 90,  # her short replies; streamed replies may run longer, since length costs no wait there
    },
    "voice": "blips",  # blips = old-school RPG talking blips while the bubble types; none = silent
    "spotify": {  # https://developer.spotify.com/dashboard (Premium). Without it, "play X" uses YouTube
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:8888/callback",
    },
    "memory": {"file": "data/memory.json", "history_turns": 12},
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    cfg = DEFAULTS
    path = Path(os.environ.get("CAPRI_CONFIG", ROOT / "config.yaml"))
    if path.exists() and yaml is not None:
        with open(path, encoding="utf-8") as f:
            cfg = _merge(DEFAULTS, yaml.safe_load(f) or {})
    DATA.mkdir(exist_ok=True)
    return cfg


def model_path(cfg: dict) -> Path:
    p = cfg["llm"].get("model_path") or ""
    return Path(p) if p else MODELS / MODEL_FILE

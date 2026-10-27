"""Capri's voice: GPT-SoVITS (ERU's copy, behind voice_server/sovits_server.py), or text only.

speak(text, on_start, on_end): on_start(seconds) fires when the audio starts, with how long it runs, so the
speech bubble can type in step with her voice and her mouth moves exactly while she talks.
"""
from __future__ import annotations

import atexit
import io
import os
import re
import subprocess
import threading

STOP = threading.Event()  # set by interrupt(): whatever she's saying stops now

# spelled the way the voice model pronounces them right (the bubble still shows the real words)
PRONOUNCE = [(r"\bchooms\b", "chewms"), (r"\bchoom\b", "chewm"), (r"\bchoombas?\b", "chewmbas"), (r"\bpreem\b", "preme"),
             (r"\beddies\b", "eddys"), (r"\bCapri\b", "Capree")]


def spoken(text: str) -> str:
    for rx, say in PRONOUNCE:
        text = re.sub(rx, say, text, flags=re.I)
    return text


def interrupt() -> None:
    STOP.set()
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass


def estimate(text: str) -> float:
    return min(9.0, 0.6 + len(text) * 0.06)


class TTS:
    def speak(self, text: str, on_start, on_end) -> None:
        raise NotImplementedError

    def prepare(self, text: str) -> None:
        """Render a line ahead of time (scripted video lines), so speaking it later starts instantly."""

    def ready(self) -> bool:
        return True


class NoTTS(TTS):
    """Text only: keep the mouth moving for roughly the time it takes to read the line."""

    def speak(self, text, on_start, on_end):
        secs = estimate(text)
        on_start(secs)
        STOP.wait(secs)
        on_end()


class GPTSoVITSTTS(TTS):
    """Capri's voice via GPT-SoVITS: ERU's own copy behind voice_server/sovits_server.py (no downloads).

    ref_audio_path / prompt_text are the reference clip and its transcript (default voices/capri/ref.wav + ref.txt).
    Any api_v2-compatible GPT-SoVITS server at `url` works too; Capri only starts one if nothing answers there.
    """

    def __init__(self, cfg: dict):
        import requests

        from ..config import ROOT

        self.http = requests.Session()
        self.proc = None
        self.cache: dict[str, tuple] = {}
        self.c = cfg["tts"]["gpt_sovits"]
        self.url = self.c["url"]
        voice = ROOT / "voices" / "capri"
        self.ref = self.c.get("ref_audio_path") or str(voice / "ref.wav")
        self.prompt = self.c.get("prompt_text") or ((voice / "ref.txt").read_text(encoding="utf-8").strip() if (voice / "ref.txt").exists() else "")
        if self._listening() or not self.c.get("autostart", True):
            return  # something is up (maybe still loading): don't start a second one
        backend = os.path.join(cfg["eru_ai_root"], "LocalAIVtuber2", "backend")
        py = os.path.join(backend, "runtime", "python.exe")
        if not os.path.exists(py):
            raise FileNotFoundError(f"ERU AI's Python not found at {py}")
        port = self.url.rsplit(":", 1)[1].split("/")[0]
        from ..config import DATA

        log = open(DATA / "voice_server.log", "a", encoding="utf-8")
        self.proc = subprocess.Popen(
            [py, "-u", str(ROOT / "voice_server" / "sovits_server.py"), "--port", port, "--eru", backend,
             "--version", self.c.get("version", "v2"), "--ref", self.ref, "--prompt-text", self.prompt,
             "--lang", self.c["prompt_lang"]],
            creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
            env=dict(os.environ, PYTORCH_JIT="0"), stdout=log, stderr=log)
        atexit.register(self.proc.terminate)
        print("[capri] starting GPT-SoVITS voice server (first line takes a minute or two) ...")

    def _health(self):
        return self.http.get(self.url.rsplit("/", 1)[0] + "/health", timeout=1).status_code

    def _listening(self) -> bool:
        try:
            self._health()
            return True
        except Exception:
            return False

    def ready(self) -> bool:
        try:
            return self._health() == 200
        except Exception:
            return False

    def _synth(self, text: str):
        if text in self.cache:
            return self.cache[text]
        import soundfile as sf

        r = self.http.post(self.url, json={
            "text": spoken(text), "text_lang": self.c["text_lang"], "ref_audio_path": self.ref,
            "prompt_text": self.prompt, "prompt_lang": self.c["prompt_lang"], "speed_factor": self.c["speed_factor"],
            "media_type": "wav", "streaming_mode": False,
        }, timeout=120)
        r.raise_for_status()
        return sf.read(io.BytesIO(r.content), dtype="float32")

    def _render(self, text: str):
        """Whole line as one clip: sentences synthesized one by one (short inputs keep the voice stable),
        joined with a small breath between them."""
        import numpy as np

        parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()] or [text]
        clips, sr = [], 32000
        for p in parts:
            audio, sr = self._synth(p)
            clips += [audio, np.zeros(int(sr * 0.18), dtype="float32")]
        return np.concatenate(clips[:-1]), sr

    def prepare(self, text: str) -> None:
        self.cache[text] = self._render(text)

    def speak(self, text, on_start, on_end):
        import sounddevice as sd

        if text not in self.cache and not self.ready():
            # server still loading (or failed): don't block her, fall back to text-only timing
            return NoTTS().speak(text, on_start, on_end)
        audio, sr = self.cache.get(text) or self._render(text)
        if not STOP.is_set():
            on_start(len(audio) / sr)
            sd.play(audio, sr)
            sd.wait()
        on_end()


def create(cfg: dict) -> TTS:
    backend = cfg["tts"]["backend"]
    try:
        if backend == "gpt_sovits":
            return GPTSoVITSTTS(cfg)
    except Exception as e:
        print(f"[capri] TTS {backend} failed, falling back to text only: {e}")
    return NoTTS()


def speak_async(tts: TTS, text: str, on_start, on_end) -> None:
    STOP.clear()

    def run():
        try:
            tts.speak(text, on_start, on_end)
        except Exception as e:
            print(f"[capri] TTS error: {e}")
            NoTTS().speak(text, on_start, on_end)

    threading.Thread(target=run, daemon=True).start()

"""Her ears: the mic, hold-to-talk or always-on, transcribed by faster-whisper ("small.en", on the GPU).

Built for low latency: the model is loaded and warmed up at boot, decoding is greedy with no timestamps and no
carried-over context, and in hold mode the transcription starts the instant you let go of the key.
"""
from __future__ import annotations

import re
import threading
import time

import numpy as np

from . import hotkey

RATE = 16000
BLOCK = 512  # 32 ms


class Transcriber:
    def __init__(self, cfg: dict):
        from faster_whisper import WhisperModel

        from ..config import MODELS
        from ..cuda import add_dlls

        add_dlls()
        c = cfg["stt"]
        name = c["model"]
        device = "cuda"
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() == 0:
                device = "cpu"
        except Exception:
            device = "cpu"
        self.model = WhisperModel(name, device=device, compute_type="int8_float16" if device == "cuda" else "int8",
                                  download_root=str(MODELS / "whisper"))
        self.hotwords = c.get("hotwords") or None
        t = time.monotonic()
        self(np.zeros(RATE, dtype=np.float32))  # warm-up: the first real line shouldn't pay for CUDA init
        print(f"[capri] ears: whisper {name} on {device}, warm in {time.monotonic() - t:.1f}s")

    def __call__(self, audio: np.ndarray) -> str:
        from ..brain.llm import GPU_LOCK

        with GPU_LOCK:  # segments are lazy: consume them inside the lock too
            segs, _ = self.model.transcribe(
                audio, language="en", beam_size=1, best_of=1, temperature=0, without_timestamps=True,
                condition_on_previous_text=False, vad_filter=False, hotwords=self.hotwords, max_new_tokens=120,
            )
            keep = [s.text.strip() for s in segs
                    if s.compression_ratio <= 2.4 and not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        text = " ".join(keep).strip()
        if hallucination(text, len(audio) / RATE, self.hotwords):
            return ""
        return text


def hallucination(text: str, seconds: float, hotwords: str | None = None) -> bool:
    """Whisper on noise invents text: the hotword list on repeat, one word over and over, more words than anyone
    can say in that time, or its favourite silence filler."""
    words = re.findall(r"[a-z0-9']+", text.lower())
    if not words:
        return False
    if len(words) / max(seconds, 0.3) > 6.5:
        return True
    if re.fullmatch(r"\W*(?:thanks? (?:you )?for watching|you|bye|\.+)\W*", text.lower()):
        return True
    run = best = 1
    for a, b in zip(words, words[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    if best >= 5 or (len(words) >= 6 and len(set(words)) / len(words) < 0.3):
        return True
    hot = set(re.findall(r"[a-z0-9']+", (hotwords or "").lower()))
    return bool(hot) and len(words) >= 2 and set(words) <= hot


def list_inputs() -> list[str]:
    """Real microphones (MME names, like Windows' Sound settings), without the mapper / virtual duplicates."""
    import sounddevice as sd

    try:
        mme = next((i for i, a in enumerate(sd.query_hostapis()) if a["name"] == "MME"), None)
        out = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and (mme is None or d["hostapi"] == mme) and "Sound Mapper" not in d["name"]:
                if d["name"] not in out:
                    out.append(d["name"])
        return out
    except Exception as e:
        print(f"[capri] can't list mics: {e}")
        return []


def resolve_input(name: str):
    if not name:
        return None
    import sounddevice as sd

    try:
        mme = next((i for i, a in enumerate(sd.query_hostapis()) if a["name"] == "MME"), None)
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and (mme is None or d["hostapi"] == mme) and name.lower() in d["name"].lower():
                return i
    except Exception as e:
        print(f"[capri] can't look up mic {name!r}: {e}")
    print(f"[capri] mic {name!r} not found, using the Windows default")
    return None


class _Vad:
    """Silero VAD per 512-sample block (works at any mic volume), or a loudness gate if it won't load."""

    def __init__(self, thresh: float):
        self.thresh = thresh
        self.model = None
        try:
            import torch
            from silero_vad import load_silero_vad

            self.model = load_silero_vad(onnx=True)
            self.torch = torch
        except Exception as e:
            print(f"[capri] silero VAD unavailable ({e}), using the loudness gate")

    def __call__(self, block: np.ndarray) -> bool:
        if self.model is not None:
            return float(self.model(self.torch.from_numpy(block.copy()), RATE).item()) > 0.5
        return float(np.sqrt(np.mean(block ** 2))) > self.thresh


class Listener(threading.Thread):
    """mode: "hold" (record while the talk key is held), "auto" (voice activity), "off".
    Callbacks run on this thread: on_text(str), on_hearing(bool), on_level(float), on_ready(state)."""

    def __init__(self, cfg: dict, settings, on_text, on_hearing, on_level=None, on_ready=None):
        super().__init__(daemon=True)
        self.cfg, self.s = cfg, settings
        self.on_text, self.on_hearing = on_text, on_hearing
        self.on_level = on_level or (lambda v: None)
        self.on_ready = on_ready or (lambda state: None)
        self.muted = False  # set while she talks in auto mode, so she doesn't hear herself
        self.stopped = False
        self.reopen = False
        self.stt = None

    @property
    def mode(self) -> str:
        return self.s["ears"]

    def run(self):
        try:
            self.stt = Transcriber(self.cfg)
        except Exception as e:
            print(f"[capri] ears failed to load: {e}")
            self.on_ready("fail")
            return
        vad = _Vad(self.cfg["stt"]["energy_threshold"])
        while not self.stopped:
            self.reopen = False
            if not self._listen(vad) and not self.reopen:
                time.sleep(2)

    def _listen(self, vad) -> bool:
        import sounddevice as sd

        mic = self.s["mic"] or self.cfg["stt"].get("input_device") or ""
        try:
            stream = sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK, device=resolve_input(mic))
        except Exception as e:
            print(f"[capri] mic {mic or 'default'} failed to open: {e}")
            self.on_ready("fail")
            return False
        print(f"[capri] mic open ({mic or 'Windows default'})")
        self.on_ready("ok")
        silence = self.cfg["stt"]["silence_seconds"]
        buf: list[np.ndarray] = []
        speaking = False
        last_voice = 0.0
        tail = 0
        n = 0
        with stream:
            while not self.stopped and not self.reopen:
                block, _ = stream.read(BLOCK)
                block = block[:, 0]
                n += 1
                if n % 3 == 0:
                    self.on_level(min(1.0, float(np.sqrt(np.mean(block ** 2))) * 12))
                mode = self.mode
                if mode == "off" or (self.muted and mode == "auto"):
                    if speaking:
                        self.on_hearing(False)
                    buf, speaking = [], False
                    continue
                done = False
                if mode == "hold":
                    try:
                        keys = hotkey.parse(self.s["talk_key"])
                    except ValueError:
                        keys = hotkey.parse("ctrl+1")
                    if hotkey.held(keys):
                        if not speaking:
                            self.on_hearing(True)
                            buf = buf[-4:]  # ~0.1 s from just before the press, so the first word isn't clipped
                        speaking, tail = True, 0
                        buf.append(block)
                        continue
                    if speaking:
                        buf.append(block)
                        tail += 1
                        done = tail >= 4  # ~0.13 s after letting go: the last syllable
                    else:
                        buf = (buf + [block])[-4:]
                else:
                    now = time.monotonic()
                    if vad(block):
                        if not speaking:
                            self.on_hearing(True)
                            buf = buf[-6:]
                        speaking, last_voice = True, now
                    if speaking:
                        buf.append(block)
                    else:
                        buf = (buf + [block])[-6:]
                    done = speaking and now - last_voice > silence
                if done:
                    speaking = False
                    self.on_hearing(False)
                    audio = np.concatenate(buf)
                    buf = []
                    if len(audio) < RATE * 0.35:
                        continue
                    t = time.monotonic()
                    text = self.stt(audio)
                    print(f"[capri] heard ({time.monotonic() - t:.2f}s for {len(audio) / RATE:.1f}s): {text!r}")
                    if text and len(text.strip(" .")) > 1:
                        self.on_text(text)
        return True

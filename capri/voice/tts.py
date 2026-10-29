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
# GPT-SoVITS gets her slang's exact sounds from voice_server/sovits_server.py (WORDS), so nothing is respelled here
PRONOUNCE: list[tuple[str, str]] = []

# the text-speak she types, said the way a person would say it out loud (read letter by letter or as odd words,
# these are what threw her voice into a different accent)
TEXT_SPEAK = {"u": "you", "ur": "your", "r": "are", "ya": "ya", "rn": "right now", "idk": "I don't know",
              "idc": "I don't care", "ngl": "not gonna lie", "fr": "for real", "ong": "on god", "tbh": "to be honest",
              "imo": "in my opinion", "bc": "because", "cuz": "cause", "pls": "please", "plz": "please",
              "thx": "thanks", "ty": "thank you", "np": "no problem", "w": "with", "wdym": "what do you mean",
              "wyd": "what you doing", "hbu": "how about you", "omg": "oh my god", "btw": "by the way",
              "smh": "shaking my head", "ik": "I know", "nvm": "never mind", "irl": "in real life", "gg": "G G",
              "lol": "", "lmao": "", "lmfao": "", "xd": "", "brb": "be right back", "afk": "away", "tmr": "tomorrow",
              "tn": "tonight", "dm": "D M", "dms": "D Ms", "pc": "P C", "ai": "A I", "yt": "YouTube"}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def sayable(text: str) -> str:
    """Her typed line as a person would say it: text-speak spelled out, emoji and stretched letters gone."""
    text = _EMOJI.sub("", text).replace("&", " and ").replace("%", " percent")
    text = re.sub(r"(\w)\1{2,}", r"\1", text)  # "sooooo" -> "so", "Hellooo" -> "Hello", "GOOOOO" -> "GO"
    # "ur" is "you're" before a verb or describing word ("ur stressing", "ur so", "ur not"), else "your"
    text = re.sub(r"\bur\b(?=\s+(?:\w+ing|so|not|gonna|right|too|a|the|being|literally|actually|crazy|insane)\b)",
                  "you're", text, flags=re.I)
    text = re.sub(r"\b[A-Za-z]+\b", lambda m: TEXT_SPEAK.get(m.group(0).lower(), m.group(0))
                  if m.group(0).lower() in TEXT_SPEAK and m.group(0) != "I" else m.group(0), text)
    return re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s{2,}", " ", text)).strip() or "Hmm."


def spoken(text: str) -> str:
    """sayable(), plus her slang respelled for GPT-SoVITS (Kokoro has lexicon-capri.txt instead)."""
    text = sayable(text)
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
        voice = ROOT / "voices" / "capri-hello"  # her three recorded hellos joined: the clip she's cloned from
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
            # her delivery: extra clips blended in, livelier sampling, and every take listened back to
            "aux_ref_audio_paths": self.c.get("aux_refs") or [], "top_k": self.c.get("top_k", 5),
            "temperature": self.c.get("temperature", 1.0), "verify": self.c.get("check_words", True),
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
            print("[capri] voice still loading: this line is text only")
            return NoTTS().speak(text, on_start, on_end)
        audio, sr = self.cache.get(text) or self._render(text)
        if not STOP.is_set():
            on_start(len(audio) / sr)
            sd.play(audio, sr)
            sd.wait()
        on_end()


class CloneTTS(TTS):
    """Her cloned voice without ERU AI: the same GPT-SoVITS v2 voice, converted to ONNX (models/voice/capri-clone)
    and run on the CPU by Genie-TTS (MIT), cloned from her three recorded hellos (assets/desk/voice/capri-ref.wav).
    Loads in the background; until then she uses text timing."""

    REF_TEXT = "Good morning, choom! Isn't it late, choom? Miss me, choom?"

    def __init__(self):
        self.genie = None
        self.warm = False  # loaded and past its first (slow) line
        self.cache: dict = {}
        self.lock = threading.Lock()  # one line at a time
        self.err = ""
        threading.Thread(target=self._load, daemon=True).start()

    @staticmethod
    def folder():
        from ..config import ROOT

        return ROOT / "models" / "voice" / "capri-clone"

    @staticmethod
    def data():
        from ..config import ROOT

        return ROOT / "models" / "voice" / "GenieData"

    @classmethod
    def installed(cls) -> bool:
        return (cls.folder() / "vits_fp32.onnx").exists() and (cls.data() / "chinese-hubert-base").exists()

    def _load(self):
        try:
            os.environ["GENIE_DATA_DIR"] = str(self.data())  # before genie_tts is imported: it reads this once
            import genie_tts as genie
            from genie_tts.Core.Inference import GENIE
            from genie_tts.ModelManager import model_manager

            from ..config import ASSETS
            from .words import WORDS

            model_manager.providers = ["CPUExecutionProvider"]  # DirectML garbled her lines; the CPU says them right
            GENIE.t2s_cpu = _capped_t2s  # a line can't run on past its text (Genie allows 10 s for anything)
            genie.load_character(character_name="capri", onnx_model_dir=str(self.folder()), language="en")
            genie.set_reference_audio(character_name="capri", audio_path=str(ASSETS / "desk" / "voice" / "capri-ref.wav"),
                                      audio_text=self.REF_TEXT, language="en")
            from genie_tts.G2P.English import EnglishG2P

            for word, phones in WORDS.items():  # her slang said right ("gonk", not "go-N-K")
                EnglishG2P._g2p_instance.cmu[word] = [phones.split()]
            self.genie = genie
            self._render("Booting up.")  # first line warms the model
            self.warm = True
            print("[capri] voice: her clone ready")
        except Exception as e:
            self.err = str(e)
            print(f"[capri] voice: her clone failed to load: {e}")

    def ready(self) -> bool:
        return self.warm

    def _render(self, text: str):
        import tempfile

        import soundfile as sf

        with self.lock:
            path = os.path.join(tempfile.gettempdir(), f"capri-line-{threading.get_ident()}.wav")
            self.genie.tts(character_name="capri", text=sayable(text), play=False, split_sentence=True, save_path=path)
            audio, sr = sf.read(path, dtype="float32")
        return audio, sr

    def prepare(self, text: str) -> None:
        if self.ready():
            self.cache[text] = self._render(text)

    def speak(self, text, on_start, on_end):
        """Sentence by sentence: the next one renders while she says this one, so you only wait for the first."""
        import queue

        import sounddevice as sd

        if text not in self.cache and not self.ready():
            print("[capri] voice still loading: this line is text only")
            return NoTTS().speak(text, on_start, on_end)
        if text in self.cache:
            parts, q = [text], queue.Queue()
            q.put(self.cache.pop(text))
        else:
            parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()] or [text]
            q = queue.Queue()

            def render():
                for p in parts:
                    if STOP.is_set():
                        break
                    q.put(self._render(p))
                q.put(None)

            threading.Thread(target=render, daemon=True).start()
        first = q.get()
        if first is not None and not STOP.is_set():
            audio, sr = first
            # the whole line's length, guessed from the first sentence (the bubble types along with it)
            on_start(len(audio) / sr * max(1.0, len(text) / max(1, len(parts[0]))))
            while True:
                sd.play(audio, sr)
                sd.wait()
                nxt = q.get() if len(parts) > 1 else None
                if nxt is None or STOP.is_set():
                    break
                audio, sr = nxt
        on_end()


def _capped_t2s(self, ref_seq, ref_bert, text_seq, text_bert, ssl_content, encoder, first_stage_decoder,
                stage_decoder):
    """Genie's T2S loop (Core/Inference.py), capped by the length of the text: about 4 sound tokens per phoneme is
    normal speech, so 8 per phoneme (plus a little) is plenty, and a take that never says it's done stops there."""
    import numpy as np

    x, prompts = encoder.run(None, {"ref_seq": ref_seq, "text_seq": text_seq, "ref_bert": ref_bert,
                                    "text_bert": text_bert, "ssl_content": ssl_content})
    y, y_emb, *present_key_values = first_stage_decoder.run(None, {"x": x, "prompts": prompts})
    names = [inp.name for inp in stage_decoder.get_inputs()]
    cap = min(500, 8 * int(text_seq.shape[-1]) + 30)
    idx = 0
    for idx in range(cap):
        if self.stop_event.is_set():
            return None
        y, y_emb, stop, *present_key_values = stage_decoder.run(None, dict(zip(names, [y, y_emb, *present_key_values])))
        if stop:
            break
    y[0, -1] = 0
    return np.expand_dims(y[:, -idx:], axis=0)


class KokoroTTS(TTS):
    """Her free voice: Kokoro-82M (Apache-2.0) through sherpa-onnx, on the CPU, offline. The same model and speaker
    as Lachy's Capri ("Her own": speaker 53 at 1.1x). Loads in the background; until then she uses text timing."""

    SPEED = 1.1

    def __init__(self, folder):
        from pathlib import Path

        self.folder = Path(folder)
        # her own voice is #53, which only Lachy's pack has; the stock model stops at 52 (53 there came out a man),
        # so without the pack she uses af_bella, the closest stock girl
        self.SPEAKER = 53 if self.folder.name == PACK else 2
        self.tts = None
        self.lock = threading.Lock()
        self.cache: dict = {}
        self.err = ""
        threading.Thread(target=self._load, daemon=True).start()

    @staticmethod
    def installed(folder) -> bool:
        from pathlib import Path

        f = Path(folder)
        return all((f / n).exists() for n in ("model.onnx", "voices.bin", "tokens.txt", "lexicon-us-en.txt"))

    def _load(self):
        try:
            import sherpa_onnx

            from ..config import ASSETS

            f = self.folder
            dicts = ",".join(str(p) for p in (f / "dict",) if p.exists())
            # her slang (choom, preem, gonk ...) isn't in Kokoro's dictionary: without these it skips the word
            words = ",".join(str(p) for p in (ASSETS / "desk" / "voice" / "lexicon-capri.txt", f / "lexicon-us-en.txt")
                             if p.exists())
            kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(f / "model.onnx"), voices=str(f / "voices.bin"), tokens=str(f / "tokens.txt"),
                data_dir=str(f / "espeak-ng-data"), lexicon=words, dict_dir=dicts, lang="en-us")
            cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=kokoro, num_threads=max(2, (os.cpu_count() or 4) // 2), provider="cpu"), max_num_sentences=1)
            self.tts = sherpa_onnx.OfflineTts(cfg)
            print("[capri] voice: Kokoro ready")
        except Exception as e:
            self.err = str(e)
            print(f"[capri] voice: Kokoro failed to load: {e}")

    def ready(self) -> bool:
        return self.tts is not None

    def _render(self, text: str):
        import numpy as np

        with self.lock:  # one line at a time: two at once crash the engine (access violation)
            audio = self.tts.generate(sayable(text), sid=self.SPEAKER, speed=self.SPEED)  # lexicon-capri.txt: her slang
        return np.asarray(audio.samples, dtype="float32"), audio.sample_rate

    def prepare(self, text: str) -> None:
        if self.ready():
            self.cache[text] = self._render(text)

    def speak(self, text, on_start, on_end):
        import sounddevice as sd

        if text not in self.cache and not self.ready():
            return NoTTS().speak(text, on_start, on_end)
        audio, sr = self.cache.pop(text, None) or self._render(text)
        if not STOP.is_set():
            on_start(len(audio) / sr)
            sd.play(audio, sr)
            sd.wait()
        on_end()


# her recorded hellos (by Lachy, PolyForm Noncommercial, like her sprites): what she says -> the file
RECORDED = {"Good morning, choom!": "hello-morning.wav", "Isn't it late, choom?": "hello-late.wav",
            "Miss me, choom?": "hello-miss.wav"}


def greeting() -> str:
    """The recorded hello for the time of day: good morning 5 am to noon, isn't it late 10 pm to 5 am, else miss me."""
    import time

    h = time.localtime().tm_hour
    return "Good morning, choom!" if 5 <= h < 12 else "Isn't it late, choom?" if h >= 22 or h < 5 else "Miss me, choom?"


def play_recorded(text: str, on_start, on_end) -> bool:
    """Plays her recorded line for `text` if there is one (in a thread). -> False if there's none."""
    from ..config import ASSETS

    name = RECORDED.get(text)
    path = ASSETS / "desk" / "voice" / name if name else None
    if not path or not path.exists():
        return False
    STOP.clear()

    def run():
        try:
            import sounddevice as sd
            import soundfile as sf

            audio, sr = sf.read(str(path), dtype="float32")
            on_start(len(audio) / sr)
            sd.play(audio, sr)
            sd.wait()
        except Exception as e:
            print(f"[capri] couldn't play {path.name}: {e}")
        on_end()

    threading.Thread(target=run, daemon=True).start()
    return True


PACK = "capri-voice-1"  # Lachy's voice pack: Kokoro with her own voice added as #53


def kokoro_dir(cfg: dict):
    """Where her free voice lives: config tts.kokoro_dir, else her voice pack in models/voice, else stock Kokoro."""
    from pathlib import Path

    from ..config import ROOT

    if cfg["tts"].get("kokoro_dir"):
        return Path(cfg["tts"]["kokoro_dir"])
    pack = ROOT / "models" / "voice" / PACK
    return pack if KokoroTTS.installed(pack) else ROOT / "models" / "voice" / "kokoro-multi-lang-v1_0"


def create(cfg: dict) -> TTS:
    backend = cfg["tts"]["backend"]
    try:
        if backend == "clone":
            if CloneTTS.installed():
                return CloneTTS()
            print("[capri] voice: her clone isn't downloaded yet; trying Kokoro")
            backend = "kokoro"
        if backend == "kokoro":
            if KokoroTTS.installed(kokoro_dir(cfg)):
                return KokoroTTS(kokoro_dir(cfg))
            print("[capri] voice: Kokoro isn't downloaded yet; text only")
            return NoTTS()
        if backend == "gpt_sovits":
            return GPTSoVITSTTS(cfg)
    except Exception as e:
        print(f"[capri] TTS {backend} failed: {e}")
        if backend == "gpt_sovits" and CloneTTS.installed():  # no ERU AI here: the same clone, on the CPU
            print("[capri] voice: using her clone (Genie) instead")
            return CloneTTS()
        if backend == "gpt_sovits" and KokoroTTS.installed(kokoro_dir(cfg)):  # no clone either: her free voice
            print("[capri] voice: using Kokoro instead")
            return KokoroTTS(kokoro_dir(cfg))
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

"""Capri's voice server: ERU AI's in-process GPT-SoVITS (v2) behind a tiny api_v2-style HTTP endpoint.

Capri starts this herself when tts.backend is gpt_sovits. By hand (ERU's Python has torch + GPT-SoVITS deps):
    set PYTORCH_JIT=0
    "D:\\ERU AI\\LocalAIVtuber2\\backend\\runtime\\python.exe" voice_server\\sovits_server.py --port 9880

ERU's code and model files are only read. GPT-SoVITS rewrites its config file on load, so it gets a copy in
Capri's data\\sovits folder, never ERU's own.

POST /tts  {"text", "text_lang", "ref_audio_path", "prompt_text", "prompt_lang", "speed_factor", ...} -> audio/wav
GET  /health -> 200 "ok" once the model is loaded and warmed up, 503 "loading" before that
"""
import argparse
import io
import json
import os
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("PYTORCH_JIT", "0")  # same as ERU: no per-length TorchScript recompiles
os.environ.setdefault("TQDM_DISABLE", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=9880)
ap.add_argument("--eru", default=r"D:\ERU AI\LocalAIVtuber2\backend")
ap.add_argument("--version", default="v2", help="v2 (ERU's default) or v3")
ap.add_argument("--ref", default=os.path.join(ROOT, "voices", "capri", "ref.wav"), help="preload + warm up with this clip")
ap.add_argument("--prompt-text", default="", help="words in --ref (default: voices/capri/ref.txt)")
ap.add_argument("--lang", default="en")
args = ap.parse_args()

BACKEND = args.eru
GSV = os.path.join(BACKEND, "services", "TTS", "GPTsovits", "GPT_SoVITS")
PRE = os.path.join(GSV, "pretrained_models")
sys.path.insert(0, BACKEND)
os.environ["PATH"] = BACKEND + os.pathsep + os.environ.get("PATH", "")  # ERU's ffmpeg, used to load the ref clip

import yaml  # noqa: E402

WEIGHTS = {
    "v2": (os.path.join(PRE, "gsv-v2final-pretrained", "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"),
           os.path.join(PRE, "gsv-v2final-pretrained", "s2G2333k.pth")),
    "v3": (os.path.join(PRE, "s1v3.ckpt"), os.path.join(PRE, "s2Gv3.pth")),
}
t2s, vits = WEIGHTS[args.version]
work = os.path.join(ROOT, "data", "sovits")
os.makedirs(work, exist_ok=True)
cfg_path = os.path.join(work, "tts_infer.yaml")
with open(cfg_path, "w", encoding="utf-8") as f:
    yaml.safe_dump({"custom": {
        "bert_base_path": os.path.join(PRE, "chinese-roberta-wwm-ext-large"),
        "cnhuhbert_base_path": os.path.join(PRE, "chinese-hubert-base"),
        "device": "cuda", "is_half": True, "version": args.version,
        "t2s_weights_path": t2s, "vits_weights_path": vits,
    }}, f)

# GPT-SoVITS finds its resources relative to the cwd (read-only): v2 from ERU's backend folder, v3 builds its
# BigVGAN path from the GPTsovits folder at import time
os.chdir(os.path.join(BACKEND, "services", "TTS", "GPTsovits") if args.version == "v3" else BACKEND)
from services.TTS.GPTsovits.GptSovits import GptSovits  # noqa: E402

engine = None
ready = threading.Event()
lock = threading.Lock()


def get_engine(ref, prompt_text, prompt_lang, text_lang):
    global engine
    if engine is None:
        engine = GptSovits(cfg_path, ref, prompt_text, prompt_lang, text_lang, cuda_graph=True)
    engine.ref_audio_path, engine.prompt_text = ref, prompt_text
    engine.prompt_lang, engine.text_lang = prompt_lang, text_lang
    return engine


def warm_up():
    """Load the model and run one throwaway line now, so her first real sentence doesn't take minutes."""
    try:
        text = args.prompt_text
        if not text:
            with open(os.path.join(ROOT, "voices", "capri", "ref.txt"), encoding="utf-8") as f:
                text = f.read().strip()
        t = time.time()
        with lock:
            get_engine(args.ref, text, args.lang, args.lang).synthesize("Booting up, choom.", -1)
        print(f"[sovits] warmed up in {time.time() - t:.1f}s", flush=True)
    except Exception as e:  # a request can still load it lazily
        print(f"[sovits] warm-up failed: {e}", flush=True)
    ready.set()


def wav_bytes(sr, audio):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.astype("int16").tobytes())
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass

    def _send(self, code, body, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.path.startswith("/health"):
            return self._send(404, b"not found")
        self._send(200, b"ok") if ready.is_set() else self._send(503, b"loading")

    def do_POST(self):
        if not self.path.startswith("/tts"):
            return self._send(404, b"not found")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with lock:
                e = get_engine(req["ref_audio_path"], req.get("prompt_text", ""),
                               req.get("prompt_lang", "en"), req.get("text_lang", "en"))
                e.speed = float(req.get("speed_factor", 1.0))
                t0 = time.time()
                sr, audio = e.synthesize(req["text"], int(req.get("seed", -1)))
                print(f"[sovits] {time.time() - t0:.2f}s for {len(audio) / sr:.2f}s of audio: {req['text'][:60]!r}", flush=True)
            self._send(200, wav_bytes(sr, audio), "audio/wav")
        except Exception as ex:  # report, keep serving
            import traceback

            traceback.print_exc()
            self._send(400, str(ex).encode("utf-8", "replace"))


threading.Thread(target=warm_up, daemon=True).start()
print(f"[sovits] GPT-SoVITS {args.version} loading, serving on 127.0.0.1:{args.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

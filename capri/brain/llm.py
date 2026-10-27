"""LLM backends. All of them take an OpenAI-style message list and return the reply text."""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import threading
from pathlib import Path

# One CUDA user at a time: llama.cpp and faster-whisper (ctranslate2) running at once in one process is
# the most likely cause of the native crashes (0xc0000005 / 0xc0000374) seen on the PC.
GPU_LOCK = threading.RLock()


class LLM:
    def chat(self, messages: list[dict], temperature: float | None = None, max_tokens: int | None = None,
             avoid: list[str] | None = None) -> str:
        """avoid: words to push down (the openers she keeps reusing); backends without logit bias ignore it."""
        raise NotImplementedError

    def stream(self, messages: list[dict], temperature: float | None = None, max_tokens: int | None = None,
               avoid: list[str] | None = None):
        """Yields the reply in pieces as it's written."""
        yield self.chat(messages, temperature, max_tokens)


def _alternate(messages: list[dict]) -> list[dict]:
    """Mistral-style templates only take an optional leading system message, then strict user/assistant
    turns. Fold anything else in so the template never raises."""
    out: list[dict] = []
    for m in messages:
        role = m["role"] if m["role"] in ("user", "assistant") else "user"
        if out and out[-1]["role"] == role:
            out[-1] = {"role": role, "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": role, "content": m["content"]})
    if out and out[0]["role"] == "assistant":
        out.insert(0, {"role": "user", "content": "(start)"})
    return out


def _find_gguf(cfg: dict) -> str:
    if cfg["llm"].get("model_path"):
        return cfg["llm"]["model_path"]
    if cfg.get("edition") == "dev":  # the portable build keeps its brains in its own models\llm
        from ..portable import brains

        hits = brains()
        if hits:
            return str(hits[0])
    llm_dir = os.path.join(cfg["eru_ai_root"], "models", "llm")
    hits = sorted(glob.glob(os.path.join(llm_dir, "**", "*.gguf"), recursive=True))
    if not hits:
        raise FileNotFoundError(f"No .gguf model found under {llm_dir}. Set llm.model_path in config.yaml.")
    return hits[0]


def _cuda_dlls() -> None:
    """ERU AI's llama-cpp build borrows torch's CUDA DLLs; make them findable without importing torch."""
    if os.name != "nt":
        return
    import importlib.util

    spec = importlib.util.find_spec("torch")
    for loc in (spec.submodule_search_locations or []) if spec else []:
        lib = os.path.join(loc, "lib")
        if os.path.isdir(lib):
            os.add_dll_directory(lib)
            os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")


class LlamaCppLLM(LLM):
    def __init__(self, cfg: dict):
        _cuda_dlls()
        from llama_cpp import Llama

        c = cfg["llm"]
        self.c = c
        path = _find_gguf(cfg)
        # Other apps share the 12 GB card (NVIDIA Broadcast, Wallpaper Engine, browsers...). If the cache doesn't fit,
        # step down instead of booting brainless: a few layers on the CPU is slower, but she still thinks.
        layers = c["n_gpu_layers"]
        # (GPU layers, 8-bit cache): the 8-bit cache (GGML_TYPE_Q8_0) halves its memory with no noticeable
        # quality loss; plain 16-bit is the fallback in case a build can't do it
        tries = [(layers, True), (layers, False)] + [(n, True) for n in (34, 28, 20) if layers < 0 or n < layers]
        err = None
        for n, q8 in tries:
            try:
                extra = {"type_k": 8, "type_v": 8} if q8 else {}
                self.model = Llama(model_path=path, n_ctx=c["n_ctx"], n_gpu_layers=n, n_batch=512,
                                   flash_attn=True, verbose=False, **extra)
                if n != layers:
                    print(f"[capri] GPU was busy: brain loaded with {n} layers on the GPU, the rest on the CPU")
                return
            except Exception as e:  # out of VRAM for the context: try the next, smaller setup
                err = e
                print(f"[capri] brain didn't load with {n} GPU layers, 8-bit cache {q8} ({e}); trying the next setup")
        raise err

    def _bias(self, avoid: list[str] | None) -> dict | None:
        """Words she keeps opening with get pushed down (the first token of each, with and without a leading space).
        Only distinctive words are passed in, so ordinary words stay usable mid-sentence."""
        if not avoid:
            return None
        out = {}
        for word in avoid:
            for variant in (word, " " + word):
                toks = self.model.tokenize(variant.encode("utf-8"), add_bos=False, special=False)
                if not toks:
                    continue
                piece = self.model.detokenize(toks[:1]).decode("utf-8", "ignore").strip()
                # only a token that's mostly this word: "Naw" -> "N" + "aw" would push down every N-word
                if len(piece) >= 3 and len(piece) >= 0.6 * len(word):
                    out[toks[0]] = -4.0
        return out or None

    def _args(self, messages, temperature, max_tokens, avoid):
        return dict(
            messages=_alternate(messages),
            temperature=self.c["temperature"] if temperature is None else temperature,
            max_tokens=max_tokens or self.c["max_tokens"],
            top_p=0.92,
            min_p=0.05,  # drops the junk tail that makes small models say random things
            repeat_penalty=1.05,
            presence_penalty=0.3,  # within a reply: don't circle back to the same words
            frequency_penalty=0.3,
            logit_bias=self._bias(avoid),
        )

    def chat(self, messages, temperature=None, max_tokens=None, avoid=None):
        with GPU_LOCK:
            out = self.model.create_chat_completion(**self._args(messages, temperature, max_tokens, avoid))
        return out["choices"][0]["message"]["content"].strip()

    def stream(self, messages, temperature=None, max_tokens=None, avoid=None):
        with GPU_LOCK:
            for chunk in self.model.create_chat_completion(**self._args(messages, temperature, max_tokens, avoid), stream=True):
                piece = chunk["choices"][0]["delta"].get("content")
                if piece:
                    yield piece


class OpenAICompatLLM(LLM):
    def __init__(self, cfg: dict):
        import requests

        self.c = cfg["llm"]
        self.session = requests.Session()

    def chat(self, messages, temperature=None, max_tokens=None, avoid=None):
        r = self.session.post(
            self.c["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {self.c['api_key']}"},
            json={
                "model": self.c["model"],
                "messages": _alternate(messages),
                "temperature": self.c["temperature"] if temperature is None else temperature,
                "max_tokens": max_tokens or self.c["max_tokens"],
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


LMS = Path.home() / ".lmstudio" / "bin" / "lms.exe"
_THINK = re.compile(r"<think>.*?(?:</think>|$)", re.S)


class LocalServerLLM(LLM):
    """Talks to a local OpenAI-style server that runs the model for her (LM Studio, llama.cpp's llama-server): same
    sampling as her llama-cpp brain, replies streamed, any <think> text dropped."""

    def __init__(self, cfg: dict, base_url: str, name: str):
        import requests

        self.c = dict(cfg["llm"])
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.name = name
        self.session = requests.Session()
        self.model = self  # the brain menu closes .model when it swaps brains

    def close(self):
        pass

    def _extra(self, avoid) -> dict:
        return {}

    def _body(self, messages, temperature, max_tokens, avoid, stream=False):
        return {"model": self.name, "messages": _alternate(messages), "stream": stream,
                "temperature": self.c["temperature"] if temperature is None else temperature,
                "max_tokens": max_tokens or self.c["max_tokens"], "top_p": 0.92, "min_p": 0.05,
                "repeat_penalty": 1.05, "presence_penalty": 0.3, "frequency_penalty": 0.3, **self._extra(avoid)}

    def chat(self, messages, temperature=None, max_tokens=None, avoid=None):
        r = self.session.post(self.url, timeout=120, json=self._body(messages, temperature, max_tokens, avoid))
        r.raise_for_status()
        return _THINK.sub("", r.json()["choices"][0]["message"].get("content") or "").strip()

    def stream(self, messages, temperature=None, max_tokens=None, avoid=None):
        with self.session.post(self.url, timeout=120, stream=True,
                               json=self._body(messages, temperature, max_tokens, avoid, stream=True)) as r:
            r.raise_for_status()
            thinking = False
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:") or line.strip() == "data: [DONE]":
                    continue
                choices = json.loads(line[5:]).get("choices") or [{}]
                piece = (choices[0].get("delta") or {}).get("content")
                if not piece:
                    continue
                if "<think>" in piece:
                    thinking = True
                if thinking:
                    if "</think>" in piece:
                        thinking, piece = False, piece.split("</think>", 1)[1]
                    else:
                        continue
                if piece:
                    yield piece


class LMStudioLLM(LocalServerLLM):
    """A GGUF her own llama-cpp is too old for (Qwen3.5 and newer), run on LM Studio's newer engine instead: it gets
    hard-linked into LM Studio's models (no copy), loaded under the name capri-brain, and she talks to LM Studio's
    local server."""

    NAME = "capri-brain"

    def __init__(self, cfg: dict, path: str):
        super().__init__(cfg, "http://127.0.0.1:1234", self.NAME)
        if not LMS.exists():
            raise RuntimeError("this model needs LM Studio (not found)")
        self._lms("server", "start")
        self._lms("unload", self.NAME)
        self._lms("import", path, "--hard-link", "-y", "--user-repo", "capri/" + Path(path).parent.name)
        key = self._key(path)
        out = self._lms("load", key, "--gpu", "max", "-c", str(self.c["n_ctx"]), "--identifier", self.NAME, "-y")
        if self.NAME not in self._lms("ps"):
            raise RuntimeError(f"LM Studio couldn't load {Path(path).name}: {out[-300:]}")

    @staticmethod
    def _lms(*args) -> str:
        r = subprocess.run([str(LMS), *args], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                           timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (r.stdout or "") + (r.stderr or "")

    def _key(self, path: str) -> str:
        """LM Studio's key for the imported file."""
        name = Path(path).stem.lower()
        try:
            for m in json.loads(self._lms("ls", "--json")):
                if name in (m.get("path", "") + " " + m.get("modelKey", "")).lower():
                    return m["modelKey"]
        except ValueError:
            pass
        return name

    def close(self):
        self._lms("unload", self.NAME)


class LlamaServerLLM(LocalServerLLM):
    """The portable build's brain: llama.cpp's own llama-server running the GGUF (any architecture its release knows,
    on Vulkan or CUDA), started and stopped with her. Thinking is switched off for models that do it."""

    PORT = 8089

    def __init__(self, cfg: dict):
        import time

        from ..config import DATA
        from ..portable import find_exe, no_window, tie_to_me

        super().__init__(cfg, f"http://127.0.0.1:{self.PORT}", "capri-brain")
        exe = find_exe("llama-server.exe")
        if exe is None:
            raise RuntimeError("her brain engine (llama.cpp) isn't downloaded yet: run Capri's setup")
        path = _find_gguf(cfg)
        DATA.mkdir(exist_ok=True)
        self.log = DATA / "llama-server.log"
        self.base = f"http://127.0.0.1:{self.PORT}"
        err = ""
        for gpu_layers in ("999", "24", "0"):  # all on the GPU, or as much as fits, or the CPU
            with open(self.log, "w", encoding="utf-8", errors="ignore") as log:
                self.proc = subprocess.Popen(
                    [str(exe), "-m", path, "--host", "127.0.0.1", "--port", str(self.PORT), "-c", str(self.c["n_ctx"]),
                     "-ngl", gpu_layers, "--jinja", "--reasoning-budget", "0", "--alias", "capri-brain"],
                    cwd=str(exe.parent), stdout=log, stderr=subprocess.STDOUT, creationflags=no_window())
            tie_to_me(self.proc)
            t = time.monotonic()
            while time.monotonic() - t < 240:
                if self.proc.poll() is not None:
                    break
                try:
                    if self.session.get(self.base + "/health", timeout=2).status_code == 200:
                        if gpu_layers != "999":
                            print(f"[capri] GPU was busy: brain running with {gpu_layers} layers on the GPU")
                        return
                except Exception:
                    pass
                time.sleep(0.5)
            self.close()
            err = self.log.read_text(encoding="utf-8", errors="ignore")[-400:]
            print(f"[capri] llama-server didn't start with {gpu_layers} GPU layers; trying the next setup")
        raise RuntimeError(f"llama-server couldn't load {Path(path).name}: {err}")

    def _extra(self, avoid) -> dict:
        """Words she keeps opening with get pushed down (the first token of each, if it's mostly that word)."""
        if not avoid:
            return {}
        bias = []
        for word in avoid:
            for variant in (word, " " + word):
                try:
                    toks = self.session.post(self.base + "/tokenize", json={"content": variant}, timeout=5).json()["tokens"]
                    if not toks:
                        continue
                    piece = self.session.post(self.base + "/detokenize", json={"tokens": toks[:1]},
                                              timeout=5).json()["content"].strip()
                except Exception:
                    continue
                if len(piece) >= 3 and len(piece) >= 0.6 * len(word):
                    bias.append([toks[0], -4.0])
        return {"logit_bias": bias} if bias else {}

    def close(self):
        proc = getattr(self, "proc", None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except Exception:
                proc.kill()


class OfflineLLM(LLM):
    """Used when nothing else loads, so the UI still runs."""

    def __init__(self, err: Exception):
        self.err = err

    def chat(self, messages, temperature=None, max_tokens=None, avoid=None):
        return f"My brain chip's not slotted, choom. LLM failed to load: {self.err}"


def create(cfg: dict) -> LLM:
    backend = cfg["llm"]["backend"]
    try:
        if backend == "llama_cpp":
            try:
                return LlamaCppLLM(cfg)
            except Exception as e:
                # too new for her llama-cpp (e.g. Qwen3.5: "unknown model architecture"): LM Studio's engine can run it
                if not LMS.exists():
                    raise
                print(f"[capri] her llama-cpp can't run this model ({e}); loading it in LM Studio instead")
                return LMStudioLLM(cfg, _find_gguf(cfg))
        if backend == "openai":
            return OpenAICompatLLM(cfg)
        if backend == "server":  # the portable build: llama.cpp's llama-server from its engines folder
            return LlamaServerLLM(cfg)
        raise ValueError(f"unknown llm backend {backend!r}")
    except Exception as e:  # keep the overlay alive even without a brain
        print(f"[capri] LLM load failed: {e}")
        return OfflineLLM(e)

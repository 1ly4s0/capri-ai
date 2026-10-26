"""LLM backends. All of them take an OpenAI-style message list and return the reply text."""
from __future__ import annotations

import threading

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


class LlamaCppLLM(LLM):
    def __init__(self, cfg: dict):
        from ..config import model_path
        from ..cuda import add_dlls

        add_dlls()
        from llama_cpp import Llama

        c = cfg["llm"]
        self.c = c
        path = str(model_path(cfg))
        import os

        if not os.path.exists(path):
            raise FileNotFoundError(f"no brain at {path}: run setup.bat (or set llm.model_path in config.yaml)")
        # Other apps share the GPU (browsers, overlays, wallpaper engines...). If the cache doesn't fit,
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
                if toks:
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
            return LlamaCppLLM(cfg)
        if backend == "openai":
            return OpenAICompatLLM(cfg)
        raise ValueError(f"unknown llm backend {backend!r}")
    except Exception as e:  # keep the overlay alive even without a brain
        print(f"[capri] LLM load failed: {e}")
        return OfflineLLM(e)

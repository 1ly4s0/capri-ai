"""Reuse of the ERU AI project on the same machine (default D:\\ERU AI).

What Capri takes from ERU AI, without writing anything into it:
- the LLM:     D:\\ERU AI\\models\\llm\\Mistral-Nemo-Instruct-2407 (loaded by brain/llm.py)
- the voice:   ERU's GPT-SoVITS, served by voice_server/sovits_server.py
- memory:      services.Memory.Memory.Memory (Qdrant + fastembed), with Capri's OWN database under data\\,
               so Eru's memories and Capri's stay separate
Each piece falls back to Capri's built-in version if ERU AI can't be imported.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading

from .config import DATA


def backend_dir(cfg: dict) -> str:
    return os.path.join(cfg["eru_ai_root"], "LocalAIVtuber2", "backend")


def _add_path(cfg: dict) -> None:
    d = backend_dir(cfg)
    if not os.path.isdir(d):
        raise FileNotFoundError(f"ERU AI backend not found at {d} (set eru_ai_root in config.yaml)")
    if d not in sys.path:
        sys.path.insert(0, d)


# ERU's services are async; run them all on one private event loop thread.
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def run(coro, timeout: float = 30):
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True, name="eru-loop").start()
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)


class EruMemory:
    """Long-term facts in a Capri-only Qdrant store, recalled by relevance to what was just said."""

    def __init__(self, cfg: dict):
        _add_path(cfg)
        from services.Memory.Memory import Memory

        # Seed Capri's embedding cache from ERU's copy (read-only) so boot never waits on a Hugging Face download.
        cache = DATA / "embed_cache"
        eru_cache = os.path.join(backend_dir(cfg), "services", "Memory", "embed_cache")
        if not cache.exists() and os.path.isdir(eru_cache):
            shutil.copytree(eru_cache, cache)
        self.mem = Memory(
            data_path=str(DATA / "eru_memory"),
            embed_cache_dir=str(DATA / "embed_cache"),
        )

    def add(self, subject: str, text: str) -> None:
        self.mem.add(subject, text, kind="fact")

    def recall(self, query: str, speaker: str) -> list[str]:
        return list(self.mem.recall(query, speaker) or [])

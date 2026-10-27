"""Long-term facts plus recent chat history, saved to a JSON "shard"."""
from __future__ import annotations

import difflib
import json
import re
import threading
import time

from ..config import ROOT


class Memory:
    def __init__(self, cfg: dict):
        self.path = ROOT / cfg["memory"]["file"]
        self.turns = cfg["memory"]["history_turns"]
        self.lock = threading.Lock()
        self.data = {"facts": [], "history": []}
        self.eru = None
        if cfg["eru"]["memory"]:
            try:
                from ..eru_bridge import EruMemory

                self.eru = EruMemory(cfg)
                print("[capri] memory: ERU AI vector memory (Capri's own store)")
            except Exception as e:
                print(f"[capri] ERU memory unavailable, using JSON facts only: {e}")
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def facts(self) -> list[str]:
        return [f["text"] for f in self.data["facts"]]

    def relevant(self, query: str, speaker: str, limit: int = 14) -> list[str]:
        """Facts worth putting in the prompt for this turn: ones that share words with what was just said, then the
        vector store's closest matches. Small talk gets none: unrelated facts make her bring up random stuff."""
        facts = self.facts()
        hard_no = [f for f in facts if "never suggest" in f.lower()][-4:]  # things you said you hate: always on
        out: list[str] = []
        if self.eru and _words(query):
            try:
                known = set(facts)
                out += [f for f in self.eru.recall(query, speaker) if f in known and f not in out][:2]
            except Exception as e:
                print(f"[capri] recall failed: {e}")
        words = _words(query) - {speaker.lower()}  # their own name matches every fact about them
        if words:
            scored = sorted(((len(words & _words(f)), i, f) for i, f in enumerate(facts)), reverse=True)
            out = list(dict.fromkeys([f for n, _, f in scored if n][:6] + out))
        out = list(dict.fromkeys(hard_no + out))
        if len(out) > len(hard_no) and _ASKS_ABOUT_ME.search(query):  # "what's my...", "do you remember...": give her the lot
            out += [f for f in reversed(facts) if f not in out]
        return out[:limit]

    def remember(self, text: str, subject: str = "user") -> None:
        text = text.strip()
        if self.eru and text:
            try:
                self.eru.add(subject, text)
            except Exception as e:
                print(f"[capri] vector memory add failed: {e}")
        with self.lock:
            if not text:
                return
            for f in self.data["facts"]:
                # same fact said again (or updated: "likes X" -> "really likes X"): keep one, the newest wording
                if difflib.SequenceMatcher(None, f["text"].lower(), text.lower()).ratio() > 0.85:
                    f["text"], f["t"] = text, time.time()
                    self._save()
                    return
            self.data["facts"].append({"text": text, "t": time.time()})
            self._save()

    def history(self) -> list[dict]:
        return self.data["history"][-self.turns * 2 :]

    def add_turn(self, user: str, assistant: str) -> None:
        with self.lock:
            self.data["history"] += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
            self.data["history"] = self.data["history"][-self.turns * 4 :]
            self._save()

    def drop_replies(self, bad) -> int:
        """Forget exchanges whose reply bad(text) flags, so a line she got stuck on stops feeding back into her."""
        with self.lock:
            h, keep, i = self.data["history"], [], 0
            while i < len(h):
                pair = h[i : i + 2]
                if len(pair) == 2 and pair[1]["role"] == "assistant" and bad(pair[1]["content"]):
                    i += 2
                    continue
                keep.append(h[i])
                i += 1
            n = (len(h) - len(keep)) // 2
            if n:
                self.data["history"] = keep
                self._save()
            return n


_ASKS_ABOUT_ME = re.compile(r"\b(?:my|me|i|remember|about me)\b", re.I)
_RULE = re.compile(r"\b(?:does not|doesn't|don't|never|hates?|dislikes?|wants? Capri to|call (?:me|him|her|them))\b", re.I)
_STOP = set("the a an and or but to of in on for with is are was were be it this that i you my your me he she they "
            "what how why when who do does did can could would should just like really so very not no yes".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']{3,}", text.lower()) if w not in _STOP}

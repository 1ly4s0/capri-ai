"""Switches you flip from her menu (ears mode, talk key, mic, DJ, vibing, eyes, chatter), kept in data/settings.json
so they survive restarts. config.yaml only gives the first-run defaults."""
from __future__ import annotations

import json

from ..config import DATA


class Settings(dict):
    def __init__(self, cfg: dict):
        d = cfg["desk"]
        super().__init__(
            ears=cfg["stt"]["mode"], talk_key=cfg["stt"]["talk_key"], mic="",
            dj=d["dj"], vibe=d["vibe"], eyes=d["eyes"], chatter=d["chatter"],
        )
        self.path = DATA / "settings.json"
        try:
            self.update({k: v for k, v in json.loads(self.path.read_text(encoding="utf-8")).items() if k in self})
        except (OSError, ValueError):
            pass

    def set(self, key, value):
        self[key] = value
        try:
            DATA.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(dict(self), indent=2), encoding="utf-8")
        except OSError as e:
            print(f"[capri] couldn't save settings: {e}")

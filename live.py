"""Entry point for Capri Live (the TikTok LIVE chat app). Its packages live in .deps-live, apart from Capri's own,
so TikTokLive's pydantic / protobuf never clash with ERU AI's."""
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
sys.path.insert(0, here)
sys.path.insert(1, os.path.join(here, ".deps-live"))
sys.path.append(os.path.join(here, ".deps"))  # PySide6
if sys.stdout is None:  # pythonw: keep a log
    os.makedirs("data", exist_ok=True)
    sys.stdout = sys.stderr = open(os.path.join("data", "live.log"), "a", encoding="utf-8", buffering=1)
runpy.run_module("capri.live", run_name="__main__")

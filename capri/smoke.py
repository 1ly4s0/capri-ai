"""Check a packaged build without starting workers, downloads or device capture."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
import traceback


def run(report_path: str) -> int:
    report: dict = {"ok": False}
    try:
        # A release check must never overwrite a user's configuration or memory.
        if not os.environ.get("CAPRI_HOME"):
            raise RuntimeError("Smoke testing requires an isolated CAPRI_HOME")
        from . import __version__
        from .config import ASSETS, ROOT, load
        from capri_dev import _first_config

        ROOT.mkdir(parents=True, exist_ok=True)
        _first_config()
        cfg = load()
        if cfg["edition"] != "dev" or cfg["llm"]["backend"] != "server":
            raise RuntimeError("The portable configuration was not bundled correctly")

        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtGui import QFontDatabase, QImage
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(["Capri-smoke-test"])
        modules = ["numpy", "requests", "yaml", "sounddevice", "soundfile", "PIL.Image", "pyperclip", "psutil",
                   "capri.desk.app", "capri.brain.agent", "capri.voice.stt"]
        if sys.platform == "win32":
            modules += ["pyaudiowpatch", "winocr", "win32api", "win32gui", "win32con"]
        for name in modules:
            importlib.import_module(name)

        images = list(ASSETS.rglob("*.png"))
        required = ["icons/capri.png", "icons/tray.png", "desk/skins/capri/idle.png",
                    "desk/skins/watcher/idle.png", "desk/splash/1.png", "desk/door/idle/1.png"]
        for name in required:
            if not (ASSETS / name).is_file():
                raise FileNotFoundError(ASSETS / name)
        for image in images:
            if QImage(str(image)).isNull():
                raise RuntimeError(f"Cannot load bundled image: {image}")
        font = ASSETS / "desk/fonts/ShareTechMono-Regular.ttf"
        if QFontDatabase.addApplicationFont(str(font)) < 0:
            raise RuntimeError(f"Cannot load bundled font: {font}")
        import soundfile

        for name in ("door_open.wav", "door_close.wav"):
            samples, _ = soundfile.read(str(ASSETS / "desk/door/sfx" / name))
            if not len(samples):
                raise RuntimeError(f"Empty bundled audio: {name}")
        app.processEvents()
        report.update(ok=True, version=__version__, edition=cfg["edition"],
                      assets=len(images), platform=sys.platform, frozen=bool(getattr(sys, "frozen", False)))
    except Exception:
        report["error"] = traceback.format_exc()
    target = Path(report_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1

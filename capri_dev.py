"""Capri, the portable dev build (Capri.exe): the setup window on the first run (pick and download her brains, ears
and engine), then her. Built with build_dev.bat."""
import os
import sys
import time


def _log():
    """No console in the exe: everything she prints goes to data\\capri.log, timestamped."""
    from capri.config import DATA

    DATA.mkdir(exist_ok=True)

    class Log:
        def __init__(self, f):
            self.f, self.fresh = f, True

        def write(self, s):
            for part in s.splitlines(keepends=True):
                if self.fresh:
                    self.f.write(time.strftime("%H:%M:%S "))
                self.f.write(part)
                self.fresh = part.endswith("\n")

        def flush(self):
            self.f.flush()

    sys.stdout = sys.stderr = Log(open(DATA / "capri.log", "a", encoding="utf-8", buffering=1))
    import faulthandler

    faulthandler.enable(open(DATA / "crash.log", "a", encoding="utf-8"), all_threads=True)


def _first_config():
    """Fresh from source: start from the dev build's settings (portable/config.yaml) if there's no config.yaml yet."""
    import shutil
    from pathlib import Path

    from capri.config import ROOT

    template = Path(__file__).resolve().parent / "portable" / "config.yaml"
    if not (ROOT / "config.yaml").exists() and template.exists():
        shutil.copy(template, ROOT / "config.yaml")


def main():
    _first_config()
    if sys.stdout is None or getattr(sys, "frozen", False):
        _log()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from capri import portable
    from capri.config import ASSETS

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(ASSETS / "icons" / "capri.png")))
    keep = {}

    def start():
        from capri.desk.app import DeskApp

        keep["desk"] = DeskApp()

    if portable.needs_setup() or "--setup" in sys.argv:
        from capri.setup import SetupWindow

        keep["setup"] = w = SetupWindow(first_run=True)
        w.done.connect(start)
        w.show()
    else:
        start()
    code = app.exec()
    sys.stdout.flush()
    os._exit(code)


if __name__ == "__main__":
    main()

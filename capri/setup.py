"""The portable build's setup window: pick her brains, her ears and the GPU engine, see how big it all is, download
it (resumable: closing halfway and reopening carries on), then she starts. Her Brain menu opens it again later to
add more."""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)

from . import portable
from .config import ROOT
from .desk.bubble import chamfer, sans

STYLE = """
QWidget { background: #110e16; color: #f2eef7; }
QLabel#h { color: #ff2e70; font-weight: 600; letter-spacing: 2px; }
QLabel#note { color: #968ca5; }
QLabel#title { color: #f2eef7; font-weight: 700; letter-spacing: 3px; }
QFrame#card { background: #1c1724; border: none; }
QFrame#card QWidget, QFrame#card QLabel, QFrame#card QCheckBox, QFrame#card QRadioButton { background: transparent; }
QCheckBox, QRadioButton { spacing: 10px; padding: 4px 0; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid #5f586c; background: #110e16; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #ff2e70; border-color: #ff2e70; }
QCheckBox:disabled { color: #968ca5; }
QPushButton { background: #ff2e70; color: white; border: none; padding: 10px 22px; font-weight: 600; }
QPushButton:disabled { background: #3a2f46; color: #968ca5; }
QPushButton#ghost { background: #261f30; color: #c9c0d6; }
QProgressBar { background: #261f30; border: none; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #ff2e70; }
"""


def gb(n: int) -> str:
    return f"{n / 2 ** 30:.1f} GB" if n >= 2 ** 30 * 0.95 else f"{n / 2 ** 20:.0f} MB"


class _Sig(QObject):
    progress = Signal(int, int, str)  # bytes done, bytes total, what
    finished = Signal(str)  # "" = ok, else the error


class Card(QFrame):
    """A section with cut corners, like her chat box."""

    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 14)
        h = QLabel(title.upper())
        h.setObjectName("h")
        h.setFont(sans(12, QFont.DemiBold))
        self.lay.addWidget(h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(28, 23, 36))
        p.drawPath(chamfer(self.rect().toRectF(), 12))
        p.fillRect(0, 16, 2, self.height() - 32, QColor(255, 46, 112))
        p.end()


def _row(widget, item: portable.Item) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    col = QVBoxLayout()
    col.setSpacing(0)
    col.addWidget(widget)
    note = QLabel(item.note)
    note.setObjectName("note")
    note.setFont(sans(12))
    note.setContentsMargins(26, 0, 0, 4)
    col.addWidget(note)
    lay.addLayout(col, 1)
    size = QLabel("installed" if item.installed() else gb(item.size))
    size.setObjectName("note")
    size.setFont(sans(13))
    lay.addWidget(size, 0, Qt.AlignTop)
    return w


class SetupWindow(QWidget):
    done = Signal()  # everything's downloaded: start her

    def __init__(self, first_run: bool = True):
        super().__init__()
        self.first_run = first_run
        self.setWindowTitle("Capri  //  setup")
        self.setStyleSheet(STYLE)
        self.setFont(sans(14))
        self.setMinimumWidth(560)
        self.sig = _Sig()
        self.sig.progress.connect(self._progress)
        self.sig.finished.connect(self._finished)
        self.cancel = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(14)
        title = QLabel("CAPRI  //  SETUP")
        title.setObjectName("title")
        title.setFont(sans(20, QFont.Bold))
        lay.addWidget(title)
        intro = QLabel("Pick what to download. Everything stays in this folder; nothing is installed on your PC.\n"
                       "Your own .gguf models go in models\\llm and show up in her Brain menu.")
        intro.setObjectName("note")
        intro.setFont(sans(13))
        lay.addWidget(intro)

        brains = Card("Brain  (pick one or more)")
        self.brain_boxes = []
        for i, it in enumerate(portable.BRAINS):
            box = QCheckBox(it.label)
            box.setFont(sans(15, QFont.DemiBold))
            box.setChecked(it.installed() or (first_run and i == 0 and not portable.brains()))
            box.setEnabled(not it.installed())
            box.toggled.connect(self._total)
            self.brain_boxes.append((box, it))
            brains.lay.addWidget(_row(box, it))
        lay.addWidget(brains)

        ears = Card("Ears  (speech to text)")
        self.ear_group = QButtonGroup(self)
        self.ear_radios = []
        have = {p.name for p in portable.ears_models()}
        for it in portable.EARS:
            r = QRadioButton(it.label)
            r.setFont(sans(15, QFont.DemiBold))
            r.setChecked(it.key == "small" if not have else Path(it.files[0][1]).name in have and it.key == "small")
            r.toggled.connect(self._total)
            self.ear_group.addButton(r)
            self.ear_radios.append((r, it))
            ears.lay.addWidget(_row(r, it))
        none = QRadioButton("None  (type to her only)")
        none.setFont(sans(15, QFont.DemiBold))
        none.toggled.connect(self._total)
        self.ear_group.addButton(none)
        ears.lay.addWidget(none)
        if not any(r.isChecked() for r, _ in self.ear_radios):
            self.ear_radios[2][0].setChecked(True)
        lay.addWidget(ears)

        engine = Card("Brain engine  (llama.cpp)")
        self.eng_group = QButtonGroup(self)
        self.eng_radios = []
        nvidia = portable.has_nvidia()
        for it in portable.ENGINE_GPU:
            r = QRadioButton(it.label + ("  (NVIDIA found)" if it.key == "cuda" and nvidia else ""))
            r.setFont(sans(15, QFont.DemiBold))
            r.setChecked(it.installed() or (it.key == "vulkan" and not any(e.installed() for e in portable.ENGINE_GPU)))
            r.toggled.connect(self._total)
            self.eng_group.addButton(r)
            self.eng_radios.append((r, it))
            engine.lay.addWidget(_row(r, it))
        lay.addWidget(engine)

        self.total = QLabel()
        self.total.setFont(sans(14, QFont.DemiBold))
        lay.addWidget(self.total)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.status = QLabel()
        self.status.setObjectName("note")
        self.status.setFont(sans(12))
        lay.addWidget(self.status)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.skip = QPushButton("Close" if not first_run else "Quit")
        self.skip.setObjectName("ghost")
        self.skip.clicked.connect(self.close)
        btns.addWidget(self.skip)
        self.go = QPushButton("Download && start Capri" if first_run else "Download")
        self.go.clicked.connect(self._start)
        btns.addWidget(self.go)
        lay.addLayout(btns)
        self._total()

    def closeEvent(self, e):
        self.cancel = True
        if self.first_run and not self.isHidden() and self.status.text() != "All set.":
            from PySide6.QtWidgets import QApplication

            QApplication.quit()  # closed before she ever started: nothing else is running
        super().closeEvent(e)

    # -- what's picked ------------------------------------------------------------------------
    def _picked(self) -> list[portable.Item]:
        items = [it for box, it in self.brain_boxes if box.isChecked() and not it.installed()]
        items += [it for r, it in self.ear_radios if r.isChecked() and not it.installed()]
        if any(r.isChecked() for r, _ in self.ear_radios) and not portable.ENGINE_EARS.installed():
            items.append(portable.ENGINE_EARS)
        items += [it for r, it in self.eng_radios if r.isChecked() and not it.installed()]
        return items

    def _total(self, *_):
        items = self._picked()
        need = sum(it.size for it in items)
        free = shutil.disk_usage(ROOT).free
        has_brain = any(box.isChecked() for box, _ in self.brain_boxes) or bool(portable.brains())
        self.total.setText(f"Download: {gb(need)}      free on this drive: {gb(free)}" if need else
                           "Everything picked is already here.")
        self.go.setEnabled(has_brain and need < free)
        if not has_brain:
            self.status.setText("Pick at least one brain.")
        elif need >= free:
            self.status.setText("Not enough space on this drive.")
        else:
            self.status.setText("")
        if not need and self.first_run:
            self.go.setText("Start Capri")

    # -- downloading ----------------------------------------------------------------------------
    def _start(self):
        items = self._picked()
        whisper = next((Path(it.files[0][1]).name for r, it in self.ear_radios if r.isChecked()), "")
        brain = next((str(ROOT / it.files[0][1]) for box, it in self.brain_boxes if box.isChecked()), "")
        self._choice = (brain, whisper)
        if not items:
            return self._finished("")
        for w in self.findChildren(QCheckBox) + self.findChildren(QRadioButton):
            w.setEnabled(False)
        self.go.setEnabled(False)
        self.skip.setText("Pause")
        self.skip.clicked.disconnect()
        self.skip.clicked.connect(self._pause)
        self.bar.show()
        threading.Thread(target=self._download, args=(items,), daemon=True).start()

    def _pause(self):
        self.cancel = True
        self.status.setText("Pausing... (it carries on where it stopped next time)")

    def _download(self, items):
        import requests

        total = sum(it.size for it in items)
        done = 0
        t0, last = time.monotonic(), 0.0
        try:
            for it in items:
                for url, rel, size in it.files:
                    dest = ROOT / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.exists() and dest.stat().st_size == size:
                        done += size
                        continue
                    part = dest.with_name(dest.name + ".part")
                    for attempt in range(30):  # flaky connections: keep resuming
                        have = part.stat().st_size if part.exists() else 0
                        if have >= size:
                            break
                        try:
                            with requests.get(url, stream=True, timeout=30, allow_redirects=True,
                                              headers={"Range": f"bytes={have}-"} if have else {}) as r:
                                r.raise_for_status()
                                if have and r.status_code != 206:  # server ignored the range: start over
                                    have = 0
                                with open(part, "ab" if have else "wb") as f:
                                    for chunk in r.iter_content(1 << 20):
                                        if self.cancel:
                                            return self.sig.finished.emit("paused")
                                        f.write(chunk)
                                        have += len(chunk)
                                        now = time.monotonic()
                                        if now - last > 0.25:
                                            last = now
                                            speed = (done + have) / max(1.0, now - t0)
                                            self.sig.progress.emit(done + have, total,
                                                                   f"{it.label}: {gb(have)} of {gb(size)}   "
                                                                   f"({speed / 2 ** 20:.1f} MB/s)")
                        except requests.RequestException as e:
                            self.sig.progress.emit(done + have, total, f"connection dropped ({type(e).__name__}), "
                                                                       f"resuming... (try {attempt + 2})")
                            time.sleep(min(30, 2 + attempt * 2))
                    if not part.exists() or part.stat().st_size != size:
                        raise RuntimeError(f"{it.label} didn't download completely")
                    part.replace(dest)
                    done += size
                portable.finish(it)
            self.sig.finished.emit("")
        except Exception as e:
            self.sig.finished.emit(f"{type(e).__name__}: {e}")

    def _progress(self, done: int, total: int, what: str):
        self.bar.setValue(round(1000 * done / max(1, total)))
        self.status.setText(what)
        self.total.setText(f"Downloading: {gb(done)} of {gb(total)}")

    def _finished(self, err: str):
        if err:
            self.status.setText("Paused. Hit Download to carry on." if err == "paused" else f"Download failed: {err}")
            self.cancel = False
            for w in self.findChildren(QCheckBox) + self.findChildren(QRadioButton):
                w.setEnabled(True)
            for box, it in self.brain_boxes:
                box.setEnabled(not it.installed())
            self.skip.setText("Close" if not self.first_run else "Quit")
            self.skip.clicked.disconnect()
            self.skip.clicked.connect(self.close)
            self._total()
            return
        from .config import load
        from .desk.settings import Settings

        s = Settings(load())
        brain, whisper = self._choice
        if brain and (self.first_run or not s["brain"]):
            s.set("brain", brain)
        if whisper:
            s.set("whisper_model", whisper)
        elif not portable.ears_models():
            s.set("ears", "off")  # "type to her only"
        self.bar.setValue(1000)
        self.status.setText("All set.")
        if self.first_run:
            self.hide()
            self.done.emit()
        else:
            self.total.setText("Downloaded. New brains are in her Brain menu.")

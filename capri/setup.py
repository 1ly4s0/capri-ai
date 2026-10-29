"""The portable build's setup window: pick her brains, her ears and the GPU engine, see how big it all is, download
it (resumable: closing halfway and reopening carries on), then she starts. Her Brain menu opens it again later to
add more."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QProgressBar, QPushButton, QRadioButton, QVBoxLayout, QWidget)

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
QLineEdit { background: #261f30; color: #f2eef7; border: none; padding: 8px 10px; }
QComboBox { background: #261f30; color: #f2eef7; border: none; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #1c1724; color: #f2eef7; selection-background-color: #ff2e70; }
QProgressBar { background: #261f30; border: none; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #ff2e70; }
"""


gb, _config_name, _set_config_name = portable.gb, portable.config_name, portable.set_config_name


class _Sig(QObject):
    progress = Signal(object, object, str)  # bytes done, bytes total, what (past 2 GB: too big for a Qt int)
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
                       "Your own .gguf models go in models/llm and show up in her Brain menu.")
        intro.setObjectName("note")
        intro.setFont(sans(13))
        lay.addWidget(intro)

        you = Card("You")
        you.lay.addWidget(QLabel("What should she call you?"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("your name or nickname")
        self.name.setFont(sans(14))
        cur = _config_name()
        if cur and cur != "you":
            self.name.setText(cur)
        you.lay.addWidget(self.name)
        if first_run:
            lay.addWidget(you)

        # her brain: download one, use a model already on this PC, or none at all (just her, no chatting)
        brains = Card("Brain")
        self.mode_group = QButtonGroup(self)
        mine = portable.local_models()
        self.mode_dl = QRadioButton("Download a brain for her")
        self.mode_mine = QRadioButton("Use a model I already have" + (f"  ({len(mine)} found on this PC)" if mine else ""))
        self.mode_none = QRadioButton("No AI  (just her: opens apps, timers, music... no chatting)")
        for r in (self.mode_dl, self.mode_mine, self.mode_none):
            r.setFont(sans(15, QFont.DemiBold))
            r.toggled.connect(self._mode)
            self.mode_group.addButton(r)
        brains.lay.addWidget(self.mode_dl)
        self.dl_box = QWidget()
        self.dl_box.setStyleSheet("background: transparent;")
        dl = QVBoxLayout(self.dl_box)
        dl.setContentsMargins(26, 0, 0, 6)
        self.brain_boxes = []
        for i, it in enumerate(portable.BRAINS):
            box = QCheckBox(it.label)
            box.setFont(sans(14, QFont.DemiBold))
            box.setChecked(it.installed() or (first_run and i == 0 and not portable.brains()))
            box.setEnabled(not it.installed())
            box.toggled.connect(self._total)
            self.brain_boxes.append((box, it))
            dl.addWidget(_row(box, it))
        brains.lay.addWidget(self.dl_box)
        brains.lay.addWidget(self.mode_mine)
        self.mine_box = QWidget()
        self.mine_box.setStyleSheet("background: transparent;")
        mrow = QHBoxLayout(self.mine_box)
        mrow.setContentsMargins(26, 0, 0, 6)
        self.mine_pick = QComboBox()
        self.mine_pick.setFont(sans(13))
        for path in mine:
            self.mine_pick.addItem(f"{path.name}   ({gb(path.stat().st_size)})", str(path))
        self.mine_pick.currentIndexChanged.connect(self._total)
        mrow.addWidget(self.mine_pick, 1)
        browse = QPushButton("Browse...")
        browse.setObjectName("ghost")
        browse.clicked.connect(self._browse)
        mrow.addWidget(browse)
        brains.lay.addWidget(self.mine_box)
        brains.lay.addWidget(self.mode_none)
        note = QLabel("No copies: she loads your model from where it is. Bigger models need more GPU memory.")
        note.setObjectName("note")
        note.setFont(sans(12))
        brains.lay.addWidget(note)
        lay.addWidget(brains)

        ears = Card("Ears  (speech to text)")
        self.ear_group = QButtonGroup(self)
        self.ear_radios = []
        have = {p.name for p in portable.ears_models()}
        for it in portable.EARS:
            r = QRadioButton(it.label)
            r.setFont(sans(15, QFont.DemiBold))
            r.setChecked(it.key == "small" and not have)
            r.toggled.connect(self._total)
            self.ear_group.addButton(r)
            self.ear_radios.append((r, it))
            ears.lay.addWidget(_row(r, it))
        none = QRadioButton("None  (type to her only)")
        none.setFont(sans(15, QFont.DemiBold))
        none.toggled.connect(self._total)
        self.ear_group.addButton(none)
        ears.lay.addWidget(none)
        if have:  # already has ears: keep those picked (small if it's there)
            mine = [(r, it) for r, it in self.ear_radios if Path(it.files[0][1]).name in have]
            next((r for r, it in mine if it.key == "small"), mine[0][0] if mine else none).setChecked(True)
        lay.addWidget(ears)

        voice = Card("Voice  (text to speech)")
        self.voice_box = QCheckBox(portable.VOICE.label)
        self.voice_box.setFont(sans(15, QFont.DemiBold))
        self.voice_box.setChecked(True)
        self.voice_box.setEnabled(not portable.VOICE.installed())
        self.voice_box.toggled.connect(self._total)
        voice.lay.addWidget(_row(self.voice_box, portable.VOICE))
        lay.addWidget(voice)

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
        (self.mode_mine if mine and not portable.brains() else self.mode_dl).setChecked(True)
        self._mode()

    def closeEvent(self, e):
        self.cancel = True
        if self.first_run and not self.isHidden() and self.status.text() != "All set.":
            from PySide6.QtWidgets import QApplication

            QApplication.quit()  # closed before she ever started: nothing else is running
        super().closeEvent(e)

    # -- what's picked ------------------------------------------------------------------------
    def _mode(self, *_):
        """Download / my own / none: only the part that applies is shown."""
        if not hasattr(self, "dl_box"):
            return
        self.dl_box.setVisible(self.mode_dl.isChecked())
        self.mine_box.setVisible(self.mode_mine.isChecked())
        self.adjustSize()
        self._total()

    def _browse(self):
        start = next((str(d) for d in portable.model_dirs()), str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(self, "Pick a model for Capri", start, "GGUF models (*.gguf)")
        if path and "mmproj" not in Path(path).name.lower():
            self.mine_pick.insertItem(0, f"{Path(path).name}   ({gb(Path(path).stat().st_size)})", path)
            self.mine_pick.setCurrentIndex(0)
            self.mode_mine.setChecked(True)

    def _brain_choice(self) -> str:
        """What she'll think with: a downloaded brain's path, your own model's path, or "none"."""
        if self.mode_none.isChecked():
            return "none"
        if self.mode_mine.isChecked():
            return self.mine_pick.currentData() or ""
        return next((str(ROOT / it.files[0][1]) for box, it in self.brain_boxes if box.isChecked()), "")

    def _picked(self) -> list[portable.Item]:
        items = [it for box, it in self.brain_boxes
                 if self.mode_dl.isChecked() and box.isChecked() and not it.installed()]
        items += [it for r, it in self.ear_radios if r.isChecked() and not it.installed()]
        if any(r.isChecked() for r, _ in self.ear_radios) and not portable.ENGINE_EARS.installed() \
                and not portable.ENGINE_EARS.system:
            items.append(portable.ENGINE_EARS)
        items += [it for r, it in self.eng_radios if r.isChecked() and not it.installed()]
        if self.voice_box.isChecked() and not portable.VOICE.installed():
            items.append(portable.VOICE)
        return items

    def _total(self, *_):
        if not hasattr(self, "go"):  # a box toggled while the window is still being built
            return
        items = self._picked()
        need = sum(it.size for it in items)
        free = shutil.disk_usage(ROOT).free
        has_brain = bool(self._brain_choice()) or (self.mode_dl.isChecked() and bool(portable.brains()))
        self.total.setText(f"Download: {gb(need)}      free on this drive: {gb(free)}" if need else
                           "Everything picked is already here.")
        self.go.setEnabled(has_brain and need < free)
        if not has_brain:
            self.status.setText("Pick a brain, your own model, or No AI.")
        elif need >= free:
            self.status.setText("Not enough space on this drive.")
        elif any(r.isChecked() for r, _ in self.ear_radios) and not portable.ENGINE_EARS.installed() \
                and portable.ENGINE_EARS.system:  # Linux: whisper.cpp comes from the package manager
            self.status.setText("Her ears also need whisper.cpp from your package manager:  sudo pacman -S whisper-cpp")
        else:
            self.status.setText("")
        if not need and self.first_run:
            self.go.setText("Start Capri")

    # -- downloading ----------------------------------------------------------------------------
    def _start(self):
        items = self._picked()
        whisper = next((Path(it.files[0][1]).name for r, it in self.ear_radios if r.isChecked()), "")
        brain = self._brain_choice()
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
        try:
            ok = portable.download(items, self.sig.progress.emit, lambda: self.cancel)
            self.sig.finished.emit("" if ok else "paused")
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

        if self.name.text().strip():
            _set_config_name(self.name.text().strip())
        s = Settings(load())
        brain, whisper = self._choice
        if brain and (self.first_run or not s["brain"] or self.mode_mine.isChecked() or brain == "none"):
            s.set("brain", brain)
            if self.mode_mine.isChecked():
                s.set("my_brains", [p for p in s["my_brains"] if p != brain] + [brain])
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

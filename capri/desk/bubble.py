"""Her speech bubble: an angular neon panel that glitches open over her head, decodes her line in, and
doubles as the type box when you click her."""
from __future__ import annotations

import math
import random
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QLineEdit, QWidget

FONT_FILE = Path(__file__).resolve().parents[2] / "assets" / "desk" / "fonts" / "ShareTechMono-Regular.ttf"
GLYPHS = "▓▒░#%&@$*+=<>/\\|01アイウエオカキクケコ"

INK = QColor(14, 6, 22, 236)
PINK = QColor(255, 20, 96)
GREEN = QColor(43, 255, 154)
CYAN = QColor(120, 250, 255)
TEXT = QColor(246, 240, 250)
MUTED = QColor(170, 150, 190)

_family = None


def mono(px: float) -> QFont:
    global _family
    if _family is None:
        fid = QFontDatabase.addApplicationFont(str(FONT_FILE))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        _family = fams[0] if fams else "Consolas"
    f = QFont(_family)
    f.setPixelSize(max(8, round(px)))
    return f


class Bubble(QWidget):
    sent = Signal(str)
    typed = Signal(str)
    nap = Signal()  # each newly revealed letter (the talking blips hang off this)

    def __init__(self, scale: float):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.s = s = scale
        self.pad = 14 * s
        self.tail = 18 * s  # room under the panel for the pointer
        self.inner_w = 300 * s
        self.font = mono(15.5 * s)
        self.small = mono(11.5 * s)
        self.text = ""
        self.user = ""
        self.shown_chars = 0.0
        self.cps = 38.0
        self.pauses, self.pause_until = False, 0.0
        self.opened_at = 0.0
        self.closing_at = 0.0
        self.hold_until = 0.0
        self.tail_x = 0.5  # 0..1 along the panel's bottom edge, points at her head
        self.tail_up = False  # panel sits below her head (no room above)
        self.typing = False
        self.thinking = False
        self.hearing = False  # the talk key is held / she hears you: show "listening" with a mic meter
        self.mic_level = 0.0

        self.edit = QLineEdit(self)
        self.edit.setFont(mono(14 * s))
        self.edit.setPlaceholderText("say something to capri...")
        self.edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,20,96,28); color: rgb(246,240,250); border: none;"
            f" border-bottom: {max(1, round(2 * s))}px solid rgb(43,255,154); padding: {round(4 * s)}px {round(6 * s)}px;"
            f" selection-background-color: rgb(255,20,96); }}")
        self.edit.returnPressed.connect(self._send)
        self.edit.hide()
        from PySide6.QtWidgets import QPushButton

        self.nap_btn = QPushButton("zZ", self)
        self.nap_btn.setToolTip("Go dormant (nap)")
        self.nap_btn.setFont(mono(13 * s))
        self.nap_btn.setCursor(Qt.PointingHandCursor)
        self.nap_btn.setStyleSheet(
            "QPushButton { background: rgb(52,245,160); color: rgb(22,10,40); border: none; font-weight: bold; }"
            "QPushButton:hover { background: rgb(255,30,110); color: white; }")
        self.nap_btn.clicked.connect(lambda: (self.close_bubble(), self.nap.emit()))
        self.nap_btn.hide()
        self.edit.installEventFilter(self)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    # -- api ----------------------------------------------------------------
    def say(self, text: str, user: str = "", secs: float | None = None, cps: float | None = None):
        """Show a line. With `secs` (how long her voice runs) it types in step with the audio and stays up
        until release(); without, it types at reading pace and closes on its own."""
        self.text, self.user = text, user
        self.thinking = False
        self.shown_chars = 0.0
        self.pauses, self.pause_until = False, 0.0
        if not self.isVisible() or self.closing_at:
            self.opened_at = time.monotonic()
        self.closing_at = 0.0
        self.pauses = cps is not None  # blip voice: little beats at commas and full stops
        self.pause_until = 0.0
        if cps:
            self.cps = cps
            self.hold_until = time.monotonic() + 3600
        elif secs:
            self.cps = max(8.0, len(text) / max(0.3, secs * 0.92))
            self.hold_until = time.monotonic() + 3600
        else:
            self.cps = 38.0
            self.hold_until = time.monotonic() + len(text) / self.cps + min(9.0, 2.6 + len(text) * 0.045)
        self._layout()
        self.show()
        self.raise_()

    def append(self, text: str):
        """The next sentence of a reply that's still being written: keep typing straight on."""
        self.text = (self.text + " " + text).strip()
        self._layout()

    def typed_all(self) -> bool:
        return self.shown_chars >= len(self.text) and time.monotonic() >= self.pause_until

    def release(self, after: float):
        """Her voice finished: keep the line up a little longer, then close."""
        self.shown_chars = len(self.text)
        if not self.typing:
            self.hold_until = time.monotonic() + after

    def listen(self, on: bool):
        if on:
            self.hearing = True
            if not self.isVisible() or self.closing_at:
                self.opened_at = time.monotonic()
            self.user, self.text, self.thinking = "", "", True
            self.closing_at = 0.0
            self.hold_until = time.monotonic() + 3600
            self._layout()
            self.show()
            self.raise_()
        else:
            self.hearing = False
            self.hold_until = time.monotonic() + 4  # nothing usable heard: close soon (think() extends it)

    def think(self, user: str):
        self.hearing = False
        self.user, self.text, self.thinking = user, "", True
        self.closing_at = 0.0
        self.hold_until = time.monotonic() + 30
        self._layout()
        self.show()

    def open_input(self):
        self.typing = True
        if not self.isVisible() or self.closing_at:
            self.text, self.user = "", ""
            self.opened_at = time.monotonic()
        self.closing_at = 0.0
        self.hold_until = time.monotonic() + 3600
        self.edit.show()
        self.nap_btn.show()
        self._layout()
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()

    def close_bubble(self):
        if self.isVisible() and not self.closing_at:
            self.closing_at = time.monotonic()
            self.typing = False
            self.edit.hide()
            self.nap_btn.hide()

    def talking(self) -> bool:
        return self.isVisible() and not self.closing_at and self.text and self.shown_chars < len(self.text)

    def place(self, head_x: float, head_y: float, screen_rect):
        """Sit above her head (or beside it near the top of the screen), always fully on screen."""
        w, h = self.width(), self.height()
        x = head_x - w * 0.35
        y = head_y - h + 22 * self.s
        self.tail_up = False
        if y < screen_rect.top() + 4:
            y = head_y + 30 * self.s
            self.tail_up = True
        x = max(screen_rect.left() + 6, min(x, screen_rect.right() - w - 6))
        self.tail_x = max(0.12, min(0.88, (head_x - x) / w))
        self.move(round(x), round(y))

    # -- internals ------------------------------------------------------------
    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == ev.Type.KeyPress and ev.key() == Qt.Key_Escape:
            self.close_bubble()
            return True
        return False

    def _send(self):
        line = self.edit.text().strip()
        self.edit.clear()
        if not line:
            return
        self.typing = False
        self.edit.hide()
        self.nap_btn.hide()
        self.sent.emit(line)

    def _lines(self, text, font, width):
        fm = QFontMetricsF(font)
        out, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            if fm.horizontalAdvance(trial) <= width or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = word
        if cur:
            out.append(cur)
        return out

    def _layout(self):
        s, pad = self.s, self.pad
        fm, sm = QFontMetricsF(self.font), QFontMetricsF(self.small)
        h = pad + 18 * s  # name tag strip
        if self.user:
            h += len(self._lines("> " + self.user, self.small, self.inner_w)) * sm.lineSpacing() + 6 * s
        body = self.text if self.text else ("..." if self.thinking else "")
        if body:
            h += len(self._lines(body, self.font, self.inner_w)) * fm.lineSpacing()
        if self.typing:
            self.edit.setGeometry(round(pad), round(h + 4 * s), round(self.inner_w - 40 * s), round(30 * s))
            self.nap_btn.setGeometry(round(pad + self.inner_w - 34 * s), round(h + 4 * s), round(34 * s), round(30 * s))
            h += 38 * s
        h += pad
        self.panel_h = h
        self.setFixedSize(round(self.inner_w + 2 * pad + 12 * s), round(h + self.tail + 12 * s))
        self.update()

    @staticmethod
    def pace(text: str, cps: float) -> float:
        """Seconds the blip voice takes to type `text` at `cps`, beats at punctuation included."""
        return len(text) / cps + 0.14 * sum(text.count(c) for c in ",;") + 0.32 * sum(text.count(c) for c in ".!?")

    def _reveal(self, now: float):
        if now < self.pause_until:
            return
        before = int(self.shown_chars)
        self.shown_chars = min(len(self.text), self.shown_chars + self.cps * 0.016)
        after = int(self.shown_chars)
        new = self.text[before:after]
        if not new:
            return
        letters = [c for c in new if c.isalnum()]
        if letters:
            self.typed.emit(letters[-1])
        if self.pauses and new[-1] in ",;.!?" and after < len(self.text):
            self.pause_until = now + (0.14 if new[-1] in ",;" else 0.32)

    def _tick(self):
        if not self.isVisible():
            return
        now = time.monotonic()
        if self.text and self.shown_chars < len(self.text):
            self._reveal(now)
        if self.closing_at and now - self.closing_at > 0.22:
            self.closing_at = 0.0
            self.hide()
            return
        if not self.typing and not self.thinking and now > self.hold_until:
            self.close_bubble()
        self.update()

    def paintEvent(self, _):
        now = time.monotonic()
        s, pad = self.s, self.pad
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.inner_w + 2 * pad
        h = self.panel_h
        ox, oy = 6 * s, (self.tail + 6 * s) if self.tail_up else 6 * s

        # open: slices slide in from the side; close: collapses to a line
        k_open = min(1.0, (now - self.opened_at) / 0.2)
        k_close = min(1.0, (now - self.closing_at) / 0.22) if self.closing_at else 0.0
        vis = k_open * (1 - k_close)
        p.translate(ox, oy + h / 2)
        p.scale(1.0, max(0.04, 1 - (1 - vis) ** 2 if k_close == 0 else 1 - k_close))
        p.translate(0, -h / 2)
        if k_open < 1:
            p.translate(random.uniform(-6, 6) * s * (1 - k_open), 0)

        c = 12 * s  # cut corners
        panel = QPolygonF([QPointF(c, 0), QPointF(w, 0), QPointF(w, h - c), QPointF(w - c, h), QPointF(0, h), QPointF(0, c)])
        path = QPainterPath()
        path.addPolygon(panel)
        path.closeSubpath()
        tx = w * self.tail_x
        tail = QPainterPath()
        if self.tail_up:
            tail.moveTo(tx - 10 * s, 0)
            tail.lineTo(tx - 2 * s, -self.tail + 2 * s)
            tail.lineTo(tx + 8 * s, 0)
        else:
            tail.moveTo(tx - 10 * s, h)
            tail.lineTo(tx - 2 * s, h + self.tail - 2 * s)
            tail.lineTo(tx + 8 * s, h)
        tail.closeSubpath()
        shape = path.united(tail)

        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawPath(shape)
        # scanlines
        p.save()
        p.setClipPath(shape)
        for yy in range(0, int(h), max(2, round(3 * s))):
            p.fillRect(QRectF(0, yy, w, 1), QColor(255, 255, 255, 7))
        p.restore()
        # neon edge (glow + crisp), with a little flicker
        flick = 0.85 + 0.15 * math.sin(now * 37) * math.sin(now * 13)
        for width, a in ((7 * s, 30), (3.5 * s, 70), (1.6 * s, 255)):
            col = QColor(PINK)
            col.setAlpha(int(a * flick))
            p.setPen(QPen(col, width, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(shape)
        # chromatic offset ghost of the edge
        p.setPen(QPen(QColor(120, 250, 255, 70), 1.2 * s))
        p.drawPath(shape.translated(2 * s, -1.5 * s))

        # name tag: green slanted plate
        tag_w, tag_h = 74 * s, 17 * s
        tag = QPolygonF([QPointF(c + 6 * s, -tag_h / 2), QPointF(c + 6 * s + tag_w, -tag_h / 2),
                         QPointF(c + tag_w - 2 * s, tag_h / 2), QPointF(c - 2 * s, tag_h / 2)])
        p.setPen(Qt.NoPen)
        p.setBrush(GREEN)
        p.drawPolygon(tag)
        p.setFont(self.small)
        p.setPen(QColor(10, 6, 16))
        p.drawText(QRectF(c, -tag_h / 2, tag_w + 6 * s, tag_h), Qt.AlignCenter, "CAPRI")
        # status dot on the right
        p.setBrush(GREEN if not self.thinking else CYAN)
        p.setPen(Qt.NoPen)
        if int(now * 2.5) % 2 or not self.thinking:
            p.drawRect(QRectF(w - pad - 6 * s, 7 * s, 6 * s, 6 * s))

        y = pad + 12 * s
        sm, fm = QFontMetricsF(self.small), QFontMetricsF(self.font)
        if self.user:
            p.setFont(self.small)
            p.setPen(MUTED)
            for line in self._lines("> " + self.user, self.small, self.inner_w):
                p.drawText(QPointF(pad, y + sm.ascent()), line)
                y += sm.lineSpacing()
            y += 6 * s
        p.setFont(self.font)
        if self.thinking and self.hearing:
            if int(now * 2.5) % 2 == 0:  # blinking REC dot
                p.setPen(Qt.NoPen)
                p.setBrush(PINK)
                p.drawEllipse(QPointF(pad + 6 * s, y + fm.ascent() * 0.62), 5 * s, 5 * s)
            p.setPen(PINK)
            p.drawText(QPointF(pad + 18 * s, y + fm.ascent()), "listening")
            bars = 10
            lit = round(min(1.0, self.mic_level * 1.6) * bars)
            bx = pad + 18 * s + fm.horizontalAdvance("listening ") + 6 * s
            for i in range(bars):
                h = (4 + i * 1.3) * s
                p.fillRect(QRectF(bx + i * 7 * s, y + fm.ascent() - h, 4.5 * s, h),
                           GREEN if i < lit else QColor(70, 50, 90))
        elif self.thinking:
            dots = "." * (1 + int(now * 4) % 3)
            p.setPen(CYAN)
            p.drawText(QPointF(pad, y + fm.ascent()), "decrypting" + dots)
        elif self.text:
            n = int(self.shown_chars)
            lines = self._lines(self.text, self.font, self.inner_w)
            left = n
            for line in lines:
                shown = line[:max(0, left)]
                rest = line[len(shown):]
                x = pad
                p.setPen(TEXT)
                p.drawText(QPointF(x, y + fm.ascent()), shown)
                x += fm.horizontalAdvance(shown)
                if rest and left >= 0:  # a few scrambled glyphs run ahead of the typed text
                    scr = "".join(random.choice(GLYPHS) if ch != " " else " " for ch in rest[:4])
                    p.setPen(PINK)
                    p.drawText(QPointF(x, y + fm.ascent()), scr)
                left -= len(line) + 1
                y += fm.lineSpacing()
        p.end()

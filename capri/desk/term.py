"""Her CMD: a little terminal that glitches onto the desktop. When you start her it boots her up and she streams
out of it; now and then she pops one open just to sit on it; when you quit she gets saved back into it and it
switches off like an old CRT.

`Typer` is the text (commands type out letter by letter, replies pop in) and `paint_cmd` draws the whole thing,
so the stream stage draws the exact same CMD inside its own window.
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .bubble import mono
from .ledges import Ledge

PINK, CYAN, GREEN = QColor(255, 20, 96), QColor(120, 250, 255), QColor(43, 255, 154)
INK, TEXT = QColor(8, 3, 13, 238), QColor(220, 210, 235)

# (line, seconds to wait after it). "{bar}" lines fill a progress bar over their wait.
BOOT = [("capri> boot --rig hibura", 0.25), ("[ ok ] relic chip .... linked", 0.18),
        ("[ ok ] personality ... 98% sane", 0.18), ("[ ok ] sass .......... overclocked", 0.18),
        ("[ !! ] yams.exe ...... denied", 0.3), ("capri> materialize", 0.15),
        ("{bar}", 0.9), ("> hold still, choom.", 0.35)]
BOOT_ALT = [("[ ok ] attitude ...... loaded x2", 0.18), ("[ ok ] desktop ....... messy", 0.18),
            ("[ ok ] coffee ........ not found", 0.18), ("[ ok ] ICE ........... bypassed", 0.18),
            ("[ ok ] night city .... 12ms, preem", 0.18)]
SAVE = [("capri> shutdown --save", 0.25), ("[ ok ] memories ...... packed", 0.2), ("{bar}", 0.7)]
SAVED = [("[ ok ] capri saved to chip", 0.3), ("> see you, choom.", 0.55), ("connection closed.", 0.5)]
EXIT = [("capri> exit", 0.35), ("> she left. rude.", 0.45)]
HOP = [[("capri> mount desktop --sit", 0.3), ("> seat deployed.", 0.2)],
       [("capri> spawn chair.exe", 0.3), ("> chair.exe? it's a terminal.", 0.2)],
       [("capri> sudo sit", 0.3), ("> fine.", 0.2)],
       [("capri> find comfy_spot", 0.3), ("> found: this window.", 0.2)]]
IDLE = [("capri> ping night_city", "reply: 12ms, preem"), ("capri> sudo be_nice", "> permission denied"),
        ("capri> breach arasaka.corp", "> 3 corpos crying"), ("capri> play --vibes max", "> nova."),
        ("capri> scan chat --for yams", "> denied. lol."), ("capri> top", "> sass 97%  patience 3%"),
        ("capri> whoami", "> best thing on this screen"), ("capri> ls ~/secrets", "> nice try."),
        ("capri> overclock --hair", "> hair at 140%"), ("capri> uptime", "> long enough to judge u")]


def color_of(line: str) -> QColor:
    if line.startswith("capri>"):
        return GREEN
    if line.startswith("[ !! ]"):
        return PINK
    if line.startswith(("[ ok ]", ">")):
        return CYAN
    return TEXT


class Typer:
    """The lines on a CMD: run() queues a script, step() plays it, done() fires when it's all out.
    With `ambient` on, an idle CMD keeps showing her little commands."""

    def __init__(self, keep: int = 5):
        self.keep = keep
        self.lines: list[list] = []  # [text, shown chars, appeared at, wait]
        self.queue: list[tuple[str, float]] = []
        self.wait_until = 0.0
        self.then = None
        self.ambient = False
        self.next_idle = 0.0

    def reset(self):
        self.lines, self.queue, self.then, self.wait_until = [], [], None, 0.0

    def run(self, items, then=None):
        self.queue += list(items)
        self.then = then

    def log(self, *lines: str):
        """Quick lines between scripts (what she's up to)."""
        self.queue += [(ln, 0.25) for ln in lines]

    def busy(self) -> bool:
        return bool(self.queue) or bool(self.lines and self.lines[-1][1] < len(self.lines[-1][0]))

    def step(self, now: float, dt: float):
        if self.lines and self.lines[-1][1] < len(self.lines[-1][0]):  # a command still typing
            self.lines[-1][1] = min(len(self.lines[-1][0]), self.lines[-1][1] + 48 * dt)
            return
        if now < self.wait_until:
            return
        if self.queue:
            text, wait = self.queue.pop(0)
            self.lines.append([text, 0 if text.startswith("capri>") else len(text), now, wait])
            self.lines = self.lines[-self.keep:]
            self.wait_until = now + wait + (len(text) / 48 if text.startswith("capri>") else 0)
            return
        if self.then:
            cb, self.then = self.then, None
            cb()
        elif self.ambient and now > self.next_idle:
            cmd, reply = random.choice(IDLE)
            self.run([(cmd, 0.4), (reply, 0.1)])
            self.next_idle = now + random.uniform(2.2, 4.0)

    def shown(self, now: float) -> list[tuple[str, QColor, float]]:
        """(text, colour, bar): bar is how full a progress-bar line is (0..1), or -1 for a text line."""
        out = []
        for text, n, t, wait in self.lines:
            if text == "{bar}":
                q = min(1.0, (now - t) / max(0.1, wait))
                out.append((f"{round(q * 100):3d}%", PINK, q))
            else:
                out.append((text[:int(n)], color_of(text), -1.0))
        return out


def paint_cmd(p: QPainter, r: QRectF, vis: float, typer: Typer, now: float, title: str = "CAPRI CMD"):
    """The CMD in `r`. vis 0..1: switching on (a line that widens, then opens up) or off (the same, backwards)."""
    if vis <= 0.001:
        return
    p.save()
    sx, sy = min(1.0, vis / 0.4), max(0.025, (vis - 0.4) / 0.6)
    jit = random.Random(int(now * 9)).random() < 0.05  # now and then the whole thing jumps a couple of pixels
    p.translate(r.center())
    p.scale(sx, sy)
    p.translate(-r.center())
    if jit or vis < 1:
        p.translate(random.uniform(-3, 3) * (1.6 - vis), 0)
    k = r.height() / 150
    if vis < 0.4:  # still just the glowing line
        for w, a in ((14 * k, 40), (6 * k, 110), (2 * k, 255)):
            p.fillRect(QRectF(r.left(), r.center().y() - w / sy / 2, r.width(), w / sy), QColor(255, 220, 240, a))
        p.restore()
        return
    bar = 22 * k
    # glow behind the frame
    for w, a in ((12 * k, 22), (6 * k, 45)):
        p.setPen(QPen(QColor(255, 20, 96, a), w))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    p.drawRect(r)
    for yy in range(int(r.top() + bar), int(r.bottom()), max(2, round(3 * k))):
        p.fillRect(QRectF(r.left(), yy, r.width(), 1), QColor(255, 255, 255, 8))
    sweep = r.top() + bar + ((now * 45 * k) % max(1.0, r.height() - bar))  # slow bright band rolling down
    p.fillRect(QRectF(r.left(), sweep, r.width(), 10 * k), QColor(120, 250, 255, 10))
    p.setBrush(PINK)
    p.drawRect(QRectF(r.left(), r.top(), r.width(), bar))
    for i in range(6):  # hazard stripes in the title bar
        x = r.right() - 112 * k - i * 9 * k
        p.setBrush(QColor(14, 6, 22, 120))
        p.drawPolygon([QPointF(x, r.top() + bar), QPointF(x + 4 * k, r.top() + bar),
                       QPointF(x + 10 * k, r.top()), QPointF(x + 6 * k, r.top())])
    f = mono(bar * 0.68)
    f.setWeight(QFont.Bold)
    p.setFont(f)
    p.setPen(QColor(14, 6, 22))
    tr = QRectF(r.left() + 8 * k, r.top(), r.width() - 16 * k, bar)
    p.drawText(tr, Qt.AlignVCenter | Qt.AlignLeft, "// " + title)
    p.drawText(tr, Qt.AlignVCenter | Qt.AlignRight, "_  [ ]  X")
    p.setPen(QPen(PINK, 1.6 * k))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r)
    p.setPen(QPen(QColor(120, 250, 255, 60), 1.0 * k))  # chromatic ghost of the frame
    p.drawRect(r.translated(2 * k, -1.5 * k))

    lines = typer.shown(now)
    lh = (r.height() - bar) / (typer.keep + 0.7)
    font = mono(min(lh * 0.74, (r.width() - 20 * k) / 34 / 0.52))  # 34 characters fit across
    p.setFont(font)
    fm = QFontMetricsF(font)
    x0 = r.left() + 10 * k
    y = r.top() + bar + lh * 0.95
    for text, col, q in lines:
        if q >= 0:  # progress bar: blocks filling up, then the percentage
            bw = r.width() - 20 * k - fm.horizontalAdvance(" 100%")
            p.fillRect(QRectF(x0, y - lh * 0.62, bw, lh * 0.55), QColor(255, 20, 96, 40))
            for i in range(int(18 * q)):
                p.fillRect(QRectF(x0 + 2 * k + i * (bw - 4 * k) / 18, y - lh * 0.56, (bw - 4 * k) / 18 - 2 * k, lh * 0.43), PINK)
            p.setPen(col)
            p.drawText(QPointF(x0 + bw + 4 * k, y), text)
        else:
            p.setPen(col)
            p.drawText(QPointF(x0, y), text)
        y += lh
    if int(now * 2.2) % 2:  # the cursor: after the line that's typing, or on a fresh prompt
        last = typer.lines[-1] if typer.lines else None
        cw, ch = fm.horizontalAdvance("M") * 0.6, fm.ascent() * 0.9
        if last and last[1] < len(last[0]):
            x = x0 + fm.horizontalAdvance(lines[-1][0])
            p.fillRect(QRectF(x + 1, y - lh - ch, cw, ch), GREEN)
        elif len(lines) < typer.keep:
            p.setPen(GREEN)
            p.drawText(QPointF(x0, y), "capri>")
            p.fillRect(QRectF(x0 + fm.horizontalAdvance("capri> "), y - ch, cw, ch), GREEN)
    p.restore()


class Term(QWidget):
    """The CMD as its own little window on your desktop. She can sit on it; drag it and she rides along."""
    closed = Signal()

    def __init__(self, k: float):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Capri CMD")
        self.k = k
        self.W, self.H = round(310 * k), round(150 * k)
        self.m = round(14 * k)  # room for the glow
        self.setFixedSize(self.W + 2 * self.m, self.H + 2 * self.m)
        self.typer = Typer(keep=5)
        self.vis, self.want = 0.0, 0.0
        self.then = None
        self.drag = None
        self.last = time.monotonic()
        self.timer = QTimer(self, interval=16, timeout=self._tick)

    # -- api ------------------------------------------------------------------
    def open_at(self, x: float, y: float, ambient: bool = True):
        """Switch on with the panel's top-left at (x, y), global coords."""
        self.typer.reset()
        self.typer.ambient = ambient
        self.typer.next_idle = time.monotonic() + 1.5
        self.then = None
        self.move(round(x - self.m), round(y - self.m))
        if not self.isVisible():
            self.vis = 0.0
        self.want = 1.0
        self.last = time.monotonic()
        self.timer.start()
        self.show()
        self.raise_()

    def close_term(self, then=None):
        """Switch off like a CRT; `then` runs once it's gone."""
        self.want = 0.0
        self.then = then
        if not self.isVisible():
            self._gone()

    def alive(self) -> bool:
        return self.isVisible() and self.want > 0

    def panel(self) -> QRect:
        """The panel in global coords."""
        return QRect(self.x() + self.m, self.y() + self.m, self.W, self.H)

    def ledge(self) -> Ledge:
        r = self.panel()
        return Ledge("term", r.left() + 0.16 * self.W, r.right() - 0.16 * self.W, r.top(), rect=r)

    def text_points(self, n: int, colors) -> list[tuple[float, float, QColor]]:
        """Points spread over the text area, for her pixels to stream in from / into."""
        r = self.panel()
        top = r.top() + 26 * self.k
        return [(random.uniform(r.left() + 12 * self.k, r.right() - 12 * self.k),
                 random.uniform(top, r.bottom() - 10 * self.k), random.choice(colors)) for _ in range(n)]

    # -- internals ----------------------------------------------------------------
    def _gone(self):
        self.timer.stop()
        self.hide()
        self.typer.reset()
        self.closed.emit()
        cb, self.then = self.then, None
        if cb:
            cb()

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last)
        self.last = now
        if self.vis < self.want:
            self.vis = min(self.want, self.vis + dt / 0.42)
        elif self.vis > self.want:
            self.vis = max(self.want, self.vis - dt / 0.32)
            if self.vis <= 0:
                return self._gone()
        if self.vis >= 1:
            self.typer.step(now, dt)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        paint_cmd(p, QRectF(self.m, self.m, self.W, self.H), self.vis, self.typer, time.monotonic())
        p.end()

    def mousePressEvent(self, e):
        pos = e.position()
        if pos.y() - self.m < 22 * self.k and pos.x() > self.m + self.W - 26 * self.k:  # the × closes it
            self.typer.reset()
            self.typer.run(EXIT[:1])
            QTimer.singleShot(250, lambda: self.close_term())
            return
        self.drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.drag = None

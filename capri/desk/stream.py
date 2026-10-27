"""Stream mode, for TikTok LIVE: she stays put (no roaming around your desktop) and the "Capri Stage" window shows just
her and her speech bubble, ready to add as a Window source in TikTok LIVE Studio.

The stage is see-through by default: nothing but her, standing on an invisible floor. Now and then a little Capri
CMD glitches in, she defrags into pixels, rebuilds sitting on top of it, hangs out a while, then hops back down and
the CMD blinks out. She's drawn live from the same sprite state as the desktop: blinks, talking, her hair glitching
to the beat. Drag her to move the stage; right-click her for the background (clear, or a cyberpunk booth / flat
green for a chroma key if your capture shows the clear parts as black) and her size.

When stream mode turns on, the CMD boots her up and she streams out of it onto her seat (same as on the desktop).

It also answers your live chat: it takes the questions the chat app (live.bat) saved, drops anything that isn't a
clean question, lets her brain pick the best one and says the answer with the viewer's question above it. A quiet
chat gets answered almost back to back; a busy one every minute or two. Comments your mods pin skip the line: she
reads those next. Yams requests get trolled on purpose.
"""
from __future__ import annotations

import json
import math
import random
import threading
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget

from ..config import DATA, ROOT
from ..live.pick import YAMS, Pool, Tail
from .term import BOOT, BOOT_ALT, EXIT, Typer, paint_cmd

BACKGROUNDS = {"clear": "Clear (just her)", "booth": "Cyberpunk booth", "green": "Green (chroma key)",
               "magenta": "Magenta (chroma key)", "black": "Black"}
FLAT = {"green": QColor(0, 255, 0), "magenta": QColor(255, 0, 255), "black": QColor(0, 0, 0)}
SIZES = {"small": (420, 600), "medium": (540, 760), "large": (720, 1000)}
LIVE_SETTINGS = DATA / "live.json"
PINK, CYAN, GREEN = QColor(255, 20, 96), QColor(120, 250, 255), QColor(43, 255, 154)
HELLO = ["Boot complete. Hey chat.", "And I'm live. Miss me, chat?", "Fresh out the terminal. Hi, chat.",
         "Online. Behave, chat. Or don't."]


class Stage(QWidget):
    def __init__(self, capri, settings):
        super().__init__(None)
        self.capri, self.s = capri, settings
        self.setWindowTitle("Capri Stage")
        self.setWindowIcon(QIcon(str(ROOT / "assets" / "icons" / "capri.png")))
        self.resize(*SIZES.get(self.s.get("stage_size", "medium"), SIZES["medium"]))
        self._clear = None
        self._apply_bg()
        self.timer = QTimer(self, interval=16, timeout=self._frame)
        self.t0 = time.monotonic()
        self.drag = None
        # the hop: where she is (floor / cmd) and what's animating
        self.spot = "floor"
        self.phase, self.phase_t = "", 0.0
        self.cmd_vis = 0.0  # 0..1, the CMD glitching in / out
        self.next_hop = time.monotonic() + random.uniform(35, 70)
        self.parts: list[list[float]] = []  # her pixels in flight: x, y, x0, y0, x1, y1, delay, colour index
        self.ghost = 1.0  # her opacity while she breaks apart / rebuilds
        self.slices = 0.0  # how glitched she looks
        self.typer = Typer(keep=5)  # what's on the CMD
        self.last_f = time.monotonic()
        self.booted = False  # the boot script finished: time to stream her out
        self.greet = False

    # -- window: clear (see-through) or painted background -------------------------------
    def _apply_bg(self):
        clear = self.s.get("stage_bg", "clear") == "clear"
        if clear == self._clear:
            return
        shown = self.isVisible()
        pos = self.pos()
        self._clear = clear
        if clear:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        else:
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setWindowFlags(Qt.Window)
            self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        if shown:
            self.move(pos)
            self.show()

    def set_bg(self, key: str):
        self.s.set("stage_bg", key)
        self._apply_bg()

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def busy(self) -> bool:
        return bool(self.phase)

    def boot(self):
        """The CMD switches on, boots her, and she streams out of it onto her seat on top of it."""
        self.spot, self.ghost, self.cmd_vis, self.parts = "floor", 0.0, 0.0, []
        self.booted, self.greet = False, True
        self.typer.reset()
        self.typer.ambient = False
        self.typer.run(BOOT[:2] + random.sample(BOOT_ALT, 2) + BOOT[2:], then=lambda: setattr(self, "booted", True))
        self.capri.sfx.play("coin")
        self._go("boot")

    # -- layout ---------------------------------------------------------------------------
    def _scale(self):
        return self.height() * 0.6 / (1.15 * self.capri.S)

    def _floor(self) -> QPointF:
        return QPointF(self.width() * 0.62, self.height() * 0.95)

    def _cmd_rect(self) -> QRectF:
        W, H = self.width(), self.height()
        return QRectF(W * 0.06, H * 0.56, W * 0.6, H * 0.2)

    def _seat(self) -> QPointF:
        r = self._cmd_rect()
        return QPointF(r.left() + r.width() * 0.55, r.top() + 2)

    def _anchor(self) -> QPointF:
        return self._seat() if self.spot == "cmd" else self._floor()

    # -- the hop: CMD in, defrag up, sit, defrag down, CMD out ------------------------------
    def _frame(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last_f)
        self.last_f = now
        c = self.capri
        t = now - self.phase_t
        if self.cmd_vis >= 1:
            self.typer.step(now, dt)
        if self.phase == "boot":
            self.cmd_vis = min(1.0, t / 0.42)
            if self.booted:
                self._launch(from_cmd=True)
                self._go("fly")
                c.sfx.play("stream")
        elif not self.phase:
            free = not c.speaking and not c.bubble.isVisible() and c.mode in ("stand", "perch")
            if free and now > self.next_hop:
                if self.spot == "floor":
                    self.typer.reset()
                    self.typer.ambient = False
                    self.typer.run([("capri> mount stage --sit", 0.3), ("> seat deployed.", 0.2)])
                    self._go("cmd_in")
                    c.sfx.play("coin")
                else:
                    self.typer.ambient = False
                    self.typer.run(EXIT)
                    self._go("out")
            elif now > self.next_hop:
                self.next_hop = now + 4  # she's busy talking: try again in a bit
        elif self.phase == "cmd_in":
            self.cmd_vis = min(1.0, t / 0.42)
            if t > 1.6:
                self._go("out")
        elif self.phase == "out":  # she breaks into pixels
            self.ghost, self.slices = max(0.0, 1 - t / 0.35), min(1.0, t / 0.2)
            if t > 0.35:
                self._launch()
                self._go("fly")
        elif self.phase == "fly":
            self._fly(t)
            if t > 0.75:
                self.parts = []
                self.spot = "cmd" if self.spot == "floor" else "floor"
                c.set_mode("perch" if self.spot == "cmd" else "stand")
                c.play("perch_glitch" if self.spot == "cmd" else "glitch")
                c.white = 0.8
                c.sfx.play("rebuild")
                self._go("in")
        elif self.phase == "in":  # she rebuilds
            self.ghost, self.slices = min(1.0, t / 0.3), max(0.0, 1 - t / 0.45)
            c.white = max(0.0, 0.8 - t * 2)
            if t > 0.5:
                c.white, self.slices, self.ghost = 0.0, 0.0, 1.0
                if self.spot == "floor":
                    self._go("cmd_out")
                else:
                    self.phase = ""
                    self.typer.ambient = True
                    self.typer.next_idle = now + 2.0
                    self.next_hop = now + random.uniform(25, 50)  # how long she hangs out up there
                    if self.greet:
                        self.greet = False
                        self.next_hop = now + random.uniform(35, 60)
                        QTimer.singleShot(400, lambda: c.say(random.choice(HELLO)))
        elif self.phase == "cmd_out":
            self.cmd_vis = max(0.0, 1 - max(0.0, t - 0.5) / 0.32)  # the exit lines show, then it switches off
            if t > 1.0:
                self.cmd_vis = 0.0
                self.phase = ""
                self.next_hop = now + random.uniform(70, 160)  # until the next time the CMD shows up
        self.update()

    def _go(self, phase):
        self.phase, self.phase_t = phase, time.monotonic()
        if phase == "out":
            self.capri.sfx.play("stream")

    def _launch(self, from_cmd=False):
        k = self._scale()
        S = self.capri.S
        a = self._anchor()
        self.spot_to = "cmd" if self.spot == "floor" else "floor"
        b = self._seat() if self.spot_to == "cmd" else self._floor()
        self.parts = []
        r = self._cmd_rect()
        for _ in range(90 if from_cmd else 70):
            if from_cmd:  # booting: her pixels pour out of the CMD's text
                x0 = random.uniform(r.left() + 10, r.right() - 10)
                y0 = random.uniform(r.top() + r.height() * 0.2, r.bottom() - 6)
            else:
                x0 = a.x() + random.uniform(-0.25, 0.25) * S * k
                y0 = a.y() - random.uniform(0.05, 1.05) * S * k
            x1 = b.x() + random.uniform(-0.25, 0.25) * S * k
            y1 = b.y() - random.uniform(0.05, 0.75 if self.spot_to == "cmd" else 1.05) * S * k
            self.parts.append([x0, y0, x0, y0, x1, y1, random.uniform(0, 0.25), random.randrange(3)])

    def _fly(self, t):
        for p in self.parts:
            q = min(1.0, max(0.0, (t - p[6]) / 0.5))
            e = q * q * (3 - 2 * q)
            arc = math.sin(math.pi * e) * 60
            p[0] = p[2] + (p[4] - p[2]) * e
            p[1] = p[3] + (p[5] - p[3]) * e - arc

    # -- drawing --------------------------------------------------------------------------
    def paintEvent(self, _):
        self._apply_bg()
        c = self.capri
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        if self._clear:
            p.setCompositionMode(QPainter.CompositionMode_Source)
            p.fillRect(self.rect(), Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        else:
            self._background(p, W, H)
        if self.cmd_vis > 0:
            self._cmd(p)
        k = self._scale()
        anchor = self._anchor()
        if self.phase != "fly" and self.ghost > 0.01:
            self._her(p, anchor, k)
        for x, y, *_rest, col in self.parts:
            p.fillRect(QRectF(x - 3, y - 3, 6, 6), (PINK, CYAN, GREEN)[int(col)])
        b = c.bubble
        if b.isVisible():
            hx, hy = c.head()
            head = QPointF(anchor.x() + (hx - c.x) * k, anchor.y() + (hy - c.y) * k)
            bk = min(1.25, max(0.7, W / (b.width() * 1.05)))  # the bubble fills the stage width, readable on a phone
            bw, bh = b.width() * bk, b.height() * bk
            x = min(max(6, head.x() - bw * 0.5), W - bw - 6)
            y = max(6, head.y() - bh + 22 * b.s * bk)
            p.save()
            p.translate(x, y)
            p.scale(bk, bk)
            b.render(p, QPoint(0, 0))
            p.restore()
        p.end()

    def _her(self, p: QPainter, anchor: QPointF, k: float):
        c = self.capri
        if self.slices < 0.02 and self.ghost > 0.99:
            p.save()
            p.translate(anchor)
            p.scale(k, k)
            p.translate(-c.A)
            c.draw(p)
            p.restore()
            return
        # glitching: draw her once into an image, then in sideways-shifted horizontal bands
        side = c.body.width()
        img = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        c.draw(q)
        q.end()
        p.save()
        p.translate(anchor)
        p.scale(k, k)
        p.translate(-c.A)
        p.setOpacity(self.ghost)
        band = max(4, side // 18)
        rng = random.Random(int(time.monotonic() * 30))
        for y in range(0, side, band):
            dx = rng.uniform(-1, 1) * 26 * self.slices if rng.random() < 0.6 else 0
            p.drawImage(QPointF(dx, y), img, QRectF(0, y, side, band))
        p.restore()

    def _cmd(self, p: QPainter):
        paint_cmd(p, self._cmd_rect(), self.cmd_vis, self.typer, time.monotonic())

    def _background(self, p: QPainter, W: int, H: int):
        bg = self.s.get("stage_bg", "clear")
        if bg in FLAT:
            p.fillRect(0, 0, W, H, FLAT[bg])
            return
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, QColor(18, 6, 30))
        g.setColorAt(0.65, QColor(40, 8, 52))
        g.setColorAt(1, QColor(12, 4, 20))
        p.fillRect(0, 0, W, H, g)
        t = time.monotonic() - self.t0
        horizon = H * 0.62
        # neon grid floor scrolling towards you
        p.setPen(QPen(QColor(255, 20, 96, 90), 1.2))
        for i in range(-12, 13):
            p.drawLine(QPointF(W / 2 + i * W * 0.04, horizon), QPointF(W / 2 + i * W * 0.32, H))
        for j in range(14):
            q = ((j + (t * 0.35) % 1) / 14) ** 2
            p.drawLine(QPointF(0, horizon + q * (H - horizon)), QPointF(W, horizon + q * (H - horizon)))
        # skyline
        p.setPen(Qt.NoPen)
        rng = random.Random(7)
        x = 0.0
        while x < W:
            w = rng.uniform(0.05, 0.12) * W
            h = rng.uniform(0.12, 0.34) * H
            p.setBrush(QColor(26, 10, 40))
            p.drawRect(QRectF(x, horizon - h, w - 3, h))
            p.setBrush(QColor(43, 255, 154, 70) if rng.random() < 0.5 else QColor(120, 250, 255, 60))
            for _ in range(rng.randint(3, 9)):
                p.drawRect(QRectF(x + rng.uniform(3, w - 9), horizon - rng.uniform(6, h - 6), 3, 4))
            x += w
        p.setBrush(QColor(255, 20, 96, 160))
        p.drawRect(QRectF(0, horizon - 1, W, 2))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(PINK, 3))
        p.drawRect(QRectF(1.5, 1.5, W - 3, H - 3))

    # -- mouse: drag her to move the stage, right-click for options --------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.drag = None

    def mouseDoubleClickEvent(self, e):
        self.next_hop = 0  # double-click: hop now

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(self.capri.menu.styleSheet())
        for key, label in BACKGROUNDS.items():
            a = m.addAction(label, lambda k=key: self.set_bg(k))
            a.setCheckable(True)
            a.setChecked(self.s.get("stage_bg", "clear") == key)
        m.addSeparator()
        for key in SIZES:
            a = m.addAction(f"Size: {key}", lambda k=key: (self.s.set("stage_size", k), self.resize(*SIZES[k])))
            a.setCheckable(True)
            a.setChecked(self.s.get("stage_size", "medium") == key)
        m.addSeparator()
        m.addAction("Hop now (CMD)", lambda: setattr(self, "next_hop", 0))
        m.popup(e.globalPos())


class Stream:
    """Turns stream mode on and off, and runs the live-chat answers while it's on."""

    def __init__(self, desk):
        self.desk, self.capri, self.s = desk, desk.capri, desk.s
        self.stage = Stage(self.capri, self.s)
        self.tail = None
        self.pool = None
        self.next_answer = 0.0
        self.last_answer_t = time.time()  # wall clock, like comment times
        self.on = False
        self.timer = QTimer(interval=2000, timeout=self._tick)

    def set(self, on: bool):
        self.on = on
        c = self.capri
        if on:
            c.roaming = False
            if c.roam_action:
                c.roam_action.setChecked(False)
            c.next_roam = 1e12
            if c.mode == "chip":
                c.wake_chip()
            # only the stage shows her: her desktop self keeps running (the stage draws from it) but goes invisible,
            # or you'd see two of her. Opacity, not hide(): a hidden bubble stops typing.
            for w in (c.body, c.bubble, c.chip):
                w.setWindowOpacity(0.0)
            self.stage.show()
            self.stage.raise_()
            self.stage.boot()
            me = self._live_settings().get("username", "")
            self.pool = Pool(me=me)
            self.tail = Tail()  # only chat from now on, nothing old
            self.next_answer = time.monotonic() + random.uniform(20, 40)
            self.timer.start()
            print("[capri] stream mode on: she stays put, Capri Stage is up")
        else:
            self.timer.stop()
            self.stage.hide()
            for w in (c.body, c.bubble, c.chip):
                w.setWindowOpacity(1.0)
            if self.stage.spot == "cmd":  # back on her feet for the desktop
                self.stage.spot = "floor"
                c.set_mode("stand")
                c.play("idle")
            self.stage.phase, self.stage.cmd_vis, self.stage.parts = "", 0.0, []
            self.stage.typer.reset()
            self.stage.ghost, self.stage.slices = 1.0, 0.0
            c.roaming = True
            if c.roam_action:
                c.roam_action.setChecked(True)
            c.next_roam = c.now + 20
            print("[capri] stream mode off")

    def _live_settings(self) -> dict:
        try:
            return json.loads(LIVE_SETTINGS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _tick(self):
        for comment in self.tail.read():
            self.pool.add(comment)
        d = self.desk
        now = time.monotonic()
        pin = self.pool.pinned_next()
        if pin is not None:  # a mod pinned it: next thing she reads
            self.next_answer = min(self.next_answer, now)
        # a fan club member or gifter asked something: they don't wait the full minute or two
        elif self.pool.vip_waiting(self.last_answer_t) and self.next_answer > now + 15:
            self.next_answer = now + random.uniform(6, 15)
        if now < self.next_answer or d.agent is None:
            return
        if not self._live_settings().get("answer", True):
            return
        c = self.capri
        if c.speaking or c.bubble.isVisible() or c.mode not in ("stand", "perch", "sleep") or self.stage.busy():
            return
        if now - d.last_talk < (6 if pin else 20):  # you two are talking: chat waits
            return
        if pin is not None:
            self.next_answer = now + self._gap()
            self.last_answer_t = time.time()
            return self._answer(None, [], pin)
        yams = self.pool.yams_ask()
        picks = self.pool.candidates()
        if not yams and not picks:
            return
        self.next_answer = now + self._gap()
        self.last_answer_t = time.time()
        self._answer(yams, picks)

    def _gap(self) -> float:
        """Seconds until the next answer: a quiet chat gets answered almost back to back (as much as she can), a busy
        one at the normal pace (chat_every in her settings)."""
        lo, hi = self.s.get("chat_every", [45, 110])
        q = self.pool.busyness()
        return random.uniform(4 + (lo - 4) * q, 10 + (hi - 10) * q)

    def _answer(self, yams, picks, pin=None):
        d = self.desk
        if not d.busy.acquire(blocking=False):
            self.next_answer = time.monotonic() + 8
            return
        goal = self.s.get("yams_goal", "like 10K")

        def work():
            try:
                t = time.monotonic()
                if pin is not None:  # pinned: no picking, she just reads it
                    c = pin
                    trolled = bool(YAMS.search(c.text))
                    if trolled:
                        d.agent.yams_flood = self.pool.yams_count()
                    text = d.agent.chat_reply(c.who, c.text, yams=trolled, goal=goal, supporter=c.supporter)
                    if not text:
                        self.pool.skip(c)
                        return
                elif yams and (not picks or random.random() < 0.5):
                    d.agent.yams_flood = self.pool.yams_count()
                    c, text = yams, d.agent.chat_reply(yams.who, yams.text, yams=True, goal=goal)
                else:
                    i = d.agent.pick_question([q.text for q in picks], [q.boost for q in picks])
                    if i is None:
                        print(f"[capri] live chat: none of {len(picks)} questions were worth it")
                        for q in picks:  # don't weigh the same ones again
                            self.pool.skip(q)
                        return
                    c = picks[i]
                    text = d.agent.chat_reply(c.who, c.text, supporter=c.supporter)
                if not text:
                    return
                self.pool.done(c, reply=text)
                shown = f"{c.who or 'chat'}: {c.text}"
                if self.stage.spot == "cmd" and self.stage.cmd_vis >= 1:
                    self.stage.typer.log(f"capri> read {'--pinned ' if c.pinned else ''}@{(c.who or 'chat')[:14]}")
                print(f"[capri] live chat ({time.monotonic() - t:.1f}s) {shown} -> {text}")
                d.bridge.replied.emit(text, shown, False)
            except Exception as e:
                print(f"[capri] live chat answer failed: {e}")
            finally:
                d.busy.release()

        threading.Thread(target=work, daemon=True).start()

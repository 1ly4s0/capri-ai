"""Capri as a desktop creature: she drops in from the top of the screen, stands on the taskbar, sits on
windows and icons, gets picked up and thrown, and every so often turns into a bolt of light and zaps
somewhere new.

Positions are her *anchor* in global logical pixels: the point between her feet when she stands, her
hip when she sits. Her window is placed so that point lands on a fixed spot of its canvas.
"""
from __future__ import annotations

import math
import random
import sys
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from . import ledges
from .bubble import Bubble
from . import sfx as sfx_mod
from .fx import CYAN, PINK, WHITE, Fx, FxLayer
from .mini import Chip, sample_chip
from .sprites import Sprites

# chat box portrait: crop size, then where her face sits relative to head() standing / sitting (units of her size)
FACE = (0.34, (0.03, 0.32), (0.08, 0.35))
BYES = ["Delta-ing out. Don't flatline without me, choom.", "Jacking out. Keep the rig warm for me.",
        "Logging off. Try not to be a gonk while I'm gone.", "Powering down. Miss me a normal amount."]
GREETING = "Ow. Okay. Whose desktop is this? ...Nice. I'm staying."
ARRIVALS = ["Comfy.", "This window's mine now.", "Don't mind me, choom.", "Better view from up here.",
            "Zap. Miss me?", "What're we working on?", None, None, None]
DEMO_REPLIES = ["Heard you loud and clear, choom.", "Ha. Say that again, I dare you.",
                "Hold on, I'm still settling into your desktop.", "Mm-hm. Noted. Filed under 'later'.",
                "You're lucky I like you."]


def _dot(x, y, floor, k):
    from .fx import P

    return P(x, y, 0.0, 0.0, 1.0, max(3, round(6 * k)), WHITE, "pixel", floor, 2200 * k, 0.6)


def ease_in_out(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Body(QWidget):
    """Her sprite window. Fully transparent pixels don't take clicks, so only she is grabbable."""

    def __init__(self, ctl: "Capri", side: int):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        self.ctl = ctl
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(side, side)
        self.setMouseTracking(False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        self.ctl.draw(p)
        p.end()

    def mousePressEvent(self, e):
        self.ctl.press(e)

    def mouseMoveEvent(self, e):
        self.ctl.drag_move(e)

    def mouseReleaseEvent(self, e):
        self.ctl.release(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.ctl.teleport()

    def contextMenuEvent(self, e):
        self.ctl.menu.popup(e.globalPos())


class Capri:
    def __init__(self, size: int = 240, roam: tuple[float, float] = (18, 40), intro: bool = True, start: bool = True):
        self.app = QApplication.instance()
        scr = QGuiApplication.primaryScreen()
        self.S = size
        self.k = size / 240  # effect scale
        self.dpr = scr.devicePixelRatio()
        self.sp = Sprites(size, self.dpr)
        self.sfx = sfx_mod.Mixer()
        self.fx = Fx(self.k)
        self.layers = [FxLayer(self.fx, s) for s in QGuiApplication.screens()]
        side = round(1.5 * size)
        self.A = QPointF(0.75 * size, 1.22 * size)  # canvas spot that sits on her anchor
        self.body = Body(self, side)
        self.bubble = Bubble(self.k)
        self.bubble.sent.connect(self.heard)
        self.bubble.typed.connect(self._typed)
        self.bubble.nap.connect(self.toggle_nap)
        self.bubble.portrait = self._portrait  # the chat box shows her live face, like a video call
        self._faces: dict = {}
        self.chip = Chip(self.k)
        self.chip.woke.connect(lambda: self.wake_chip())
        self.chip.moved.connect(self._chip_moved)
        self.chip_pos = None  # where the chip naps; None = bottom-left corner
        self.blips = False  # the app turns this on when she "talks" in blips instead of a voice
        self.blip_n = 0
        self.on_user = None  # set by the app: what happens with a line typed to her (the brain)
        self.voice = None  # set by the app: voice(text, on_start(seconds), on_end) speaks a line out loud
        self.speaking = False
        self.on_settled = None  # called once the next time she comes to rest (the video script waits on it)
        self.quit_fn = self.app.quit  # the app swaps in one that also stops the voice server
        self.talk_open = False  # a streamed reply is still coming in
        self.talk_timer = None
        self.beat = None  # set by the app: () -> (pulse 0..1, music playing) from the ear on your speakers
        self.vibe = 0.0

        self.mode = "hidden"  # intro | stand | perch | held | fall | charge | travel | appear | sleep
        self.x, self.y = 0.0, 0.0
        self.vx = self.vy = 0.0
        self.seat: ledges.Ledge | None = None
        self.clip, self.clip_t = "idle", 0.0
        self.cycle = -1
        self.blink = None
        self.mouth = -1
        self.frame, self.shown = 0, "idle"
        self.sx = self.sy = 1.0
        self.angle = 0.0
        self.white = 0.0
        self.squash_t = -1.0
        self.t0 = time.monotonic()
        self.now = 0.0
        self.st = 0.0  # time the current mode started
        self.ledge_list: list[ledges.Ledge] = []
        self.ledges_at = -9.0
        self.lost_since = -1.0
        self.roam = roam
        self.roaming = True
        self.next_roam = 0.0
        self.last_touch = 0.0
        self.press_at = None
        self.grab = QPointF()
        self.hist: list[tuple[float, float, float]] = []
        self.intro_only_floor = False
        self.target = None
        self.say_after = None

        self._build_menu()
        self._build_tray()
        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(15)
        self.last = time.monotonic()
        if sys.platform == "win32":
            self.top_timer = QTimer()
            self.top_timer.timeout.connect(self._topmost)
            self.top_timer.start(1500)
        if intro:
            QTimer.singleShot(400, self.drop_in)
        elif start:
            g = ledges.work_area(scr)
            self._land_floor(g.right() - 0.3 * g.width(), g.bottom() + 1, quiet=True)

    # -- small helpers ------------------------------------------------------------
    def skip(self):
        return {int(w.winId()) for w in [self.body, self.bubble, self.chip] + self.layers}

    def refresh_ledges(self, force=False):
        if force or self.now - self.ledges_at > 0.3:
            self.ledges_at = self.now
            try:
                self.ledge_list = ledges.find(self.skip(), True, self.now)
            except Exception as e:  # never let a weird window kill her
                print("ledges:", e)
                self.ledge_list = ledges.floors()

    def screen_rect(self, x, y) -> QRect:
        scr = QGuiApplication.screenAt(QPointF(x, y).toPoint()) or QGuiApplication.primaryScreen()
        return ledges.work_area(scr)

    def cur(self):
        return self.sp[self.clip]

    def play(self, name):
        if name != self.clip:
            self.clip, self.clip_t = name, self.now
            self.cycle = -1

    def set_mode(self, m):
        self.mode, self.st = m, self.now

    def center(self):
        """Middle of her body, global coords (for effects)."""
        up = 0.38 if self.mode == "perch" else 0.5
        return self.x + (0.1 if self.mode == "perch" else -0.05) * self.S, self.y - up * self.S

    def head(self):
        if self.mode == "perch" or self.clip.startswith("perch"):
            return self.x + 0.14 * self.S, self.y - 0.64 * self.S
        return self.x - 0.07 * self.S, self.y - 1.03 * self.S

    def standing_clip(self):
        if self.mode == "perch":  # also sitting on the stream stage's CMD, where her desktop seat is still the floor
            return "perch"
        return "perch" if self.seat is not None and self.seat.kind != "floor" else "idle"

    def _portrait(self):
        """Her face right now for the call-style chat box: the current frame (blinks, talking mouth) cropped around
        her head. None while she's not on screen (the box keeps the last face)."""
        if self.mode in ("hidden", "chip", "to_chip", "stream", "intro"):
            return None
        key = (self.shown, self.frame, self.mouth)
        if key in self._faces:
            return self._faces[key]
        c = self.sp[self.shown]
        ax, ay = c.anchor
        hx, hy = self.head()
        cx, cy = hx - (self.x - ax * c.w), hy - (self.y - ay * c.h)  # her head in the frame's own pixels
        side = FACE[0] * self.S
        fx, fy = FACE[2] if self.shown.startswith("perch") else FACE[1]
        src = QRectF(cx + fx * self.S - side / 2, cy + fy * self.S - side / 2, side, side)
        out = QPixmap(round(side * self.dpr), round(side * self.dpr))
        out.setDevicePixelRatio(self.dpr)
        out.fill(Qt.transparent)
        q = QPainter(out)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        q.translate(-src.topLeft())
        q.drawPixmap(0, 0, c.frames[self.frame])
        if self.mouth >= 0:
            q.drawPixmap(0, 0, self.sp["mouth"].frames[self.mouth])
        q.end()
        if len(self._faces) > 200:
            self._faces.clear()
        self._faces[key] = out
        return out

    # -- per-frame ----------------------------------------------------------------
    def tick(self):
        t = time.monotonic()
        dt = min(0.05, t - self.last)
        self.last = t
        self.now = t - self.t0
        m = self.mode
        if m == "intro":
            self._intro_step()
        elif m == "fall":
            self._fall_step(dt)
        elif m == "held":
            self._held_step()
        elif m == "charge":
            self._charge_step()
        elif m == "stream":
            if self.now - self.st >= self.stream_T - 0.05:
                self.arrive()
        elif m == "to_chip":
            if self.now - self.st >= self.stream_T - 0.05:
                self._chip_arrive()
        elif m == "chip":
            self._chip_step()
        elif m == "appear":
            self._appear_step()
        elif m == "bye":
            self._bye_step()
        elif m in ("stand", "perch", "sleep"):
            self._rest_step()
        pulse, playing = self.beat() if self.beat else (0.0, False)
        target = pulse if playing else 0.0
        self.vibe = max(target, self.vibe * 0.88)
        self.fx.step(dt)
        for layer in self.layers:
            layer.refresh()
        self._animate()
        if self.mode != "hidden" and self.body.isVisible():
            self._place()
            self.body.update()
        if self.bubble.isVisible():
            hx, hy = self.head()
            self.bubble.place(hx, hy, self.screen_rect(hx, self.y - 10))

    def _place(self):
        self.body.move(round(self.x - self.A.x()), round(self.y - self.A.y()))

    def _animate(self):
        """Pick the frame for this tick: clip timing, blinks during idle loops, mouth flaps while talking."""
        c = self.cur()
        i = int((self.now - self.clip_t) * c.fps)
        if self.clip in ("glitch", "perch_glitch", "wake") and i >= c.count:
            self.play(self.standing_clip() if self.mode != "sleep" else "idle")
            c, i = self.cur(), 0
        if self.clip == "grin" and i >= c.count * 2:
            self.play("idle")
            c, i = self.cur(), 0
        if self.clip in ("idle", "perch"):
            cyc = i // c.count
            if cyc != self.cycle:
                self.cycle = cyc
                r = random.random()
                pre = "perch_" if self.clip == "perch" else ""
                self.blink = (pre + ("blink_glitch" if r < 0.08 else "blink")) if r < 0.45 else None
                if self.clip == "idle" and r > 0.95 and self.mode == "stand" and not self.bubble.isVisible():
                    self.play("grin")
                    return self._animate()
        self.frame = i % c.count
        self.shown = self.clip
        if self.blink and self.clip in ("idle", "perch") and 6 <= self.frame < 10:
            self.shown, self.frame = self.blink, self.frame - 6
        self.mouth = -1
        if self.speaking and self.shown == "idle":
            self.mouth = int(self.now * 12 + 0.5) % 5 if int(self.now * 12) % 4 else 0

    def draw(self, p: QPainter):
        if self.mode in ("hidden", "chip", "to_chip"):
            return
        c = self.sp[self.shown]
        pm = c.frames[self.frame]
        ax, ay = c.anchor
        breathe = tilt = 0.0
        if self.mode in ("stand", "perch"):
            breathe = math.sin(self.now * 1.75) * 2.0 * self.k
            tilt = math.sin(self.now * 0.95) * 0.6
        sx, sy = self.sx, self.sy
        if self.squash_t >= 0:  # landing squash: flatten, overshoot, settle
            q = (self.now - self.squash_t) / 0.42
            if q >= 1:
                self.squash_t = -1
            else:
                amt = self.squash_amt * math.exp(-5 * q) * math.cos(q * 9)
                sy *= 1 - amt
                sx *= 1 + amt * 0.7
        p.translate(self.A)
        p.translate(0, (breathe if self.mode == "stand" else 0) - self.vibe * 3 * self.k)
        p.rotate(self.angle + tilt)
        mid = 0.5 * self.S if self.mode == "bye" else 0.0
        p.translate(0, -mid)
        p.scale(sx, sy)
        p.translate(0, mid)
        if self.mode == "perch":
            p.translate(0, breathe * 0.5)
        tl = QPointF(-ax * c.w, -ay * c.h)
        if self.white > 0.02:  # electric aura behind her while charging / materialising
            p.save()
            p.setOpacity(min(1.0, self.white) * 0.55)
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                p.drawPixmap(tl + QPointF(dx * self.k, dy * self.k), c.white(self.frame))
            p.restore()
        if self.vibe > 0.35 and self.mode in ("stand", "perch") and self.white < 0.05:
            pm = self._vibed(c, pm)  # on the beat: bands of her hair jump sideways
        p.drawPixmap(tl, pm)
        if self.mouth >= 0:
            p.drawPixmap(tl, self.sp["mouth"].frames[self.mouth])
        if self.white > 0.02:
            p.setOpacity(min(1.0, self.white))
            p.drawPixmap(tl, c.white(self.frame))
            p.setOpacity(1.0)

    def _vibed(self, c, pm):
        """A copy of the frame with two or three bands of her hair moved sideways (moved, not copied on top, so
        she never looks doubled). Same tear for a few frames so it reads as a glitch, not noise."""
        out = QPixmap(pm.size())
        out.setDevicePixelRatio(pm.devicePixelRatio())
        out.fill(Qt.transparent)
        q = QPainter(out)
        q.drawPixmap(0, 0, pm)
        d, k, v = c.dpr, self.k, self.vibe
        top, bottom = c.h * (0.03 if self.mode == "stand" else 0.16), c.h * (0.42 if self.mode == "stand" else 0.45)
        rnd = random.Random(int(self.now * 12))
        for _ in range(2 + (v > 0.7)):
            hh = rnd.uniform(5, 14) * k
            y0 = rnd.uniform(top, bottom - hh)
            dx = rnd.choice((-1, 1)) * rnd.uniform(3, 9) * k * v
            band = QRectF(0, y0, c.w, hh)
            q.setCompositionMode(QPainter.CompositionMode_Clear)
            q.fillRect(band, Qt.transparent)
            q.setCompositionMode(QPainter.CompositionMode_SourceOver)
            q.drawPixmap(band.translated(dx, 0), pm, QRectF(0, y0 * d, pm.width(), hh * d))
        q.end()
        return out

    def listening(self, on: bool):
        """Talk key held (or she caught your voice): the bubble shows a REC dot and your mic level."""
        if on:
            self.sfx.play("pop")
            self.next_roam = max(self.next_roam, self.now + 30)
            hx, hy = self.head()
            self.bubble.listen(True)
            self.bubble.place(hx, hy, self.screen_rect(hx, self.y - 10))
        else:
            self.bubble.listen(False)

    # -- intro: the sky tears open and she drops out ------------------------------
    def drop_in(self, greet=True, x_frac=None):
        self.bubble.close_bubble()
        scr = QGuiApplication.primaryScreen()
        g, work = scr.geometry(), ledges.work_area(scr)
        self.ix = work.left() + work.width() * (x_frac if x_frac is not None else random.uniform(0.58, 0.82))
        self.iy = g.top()
        self.body.hide()
        self.seat = None
        self.say_after = GREETING if greet else None
        self.set_mode("intro")
        self.stage = 0
        self.sfx.play("tear")
        self.fx.glitch_band(self.ix - 260 * self.k, self.ix + 260 * self.k, self.iy, self.iy + 40 * self.k, life=0.5)

    def _intro_step(self):
        t = self.now - self.st
        k, x, y = self.k, self.ix, self.iy
        if self.stage == 0:  # the tear: crackling along the top edge, getting wider
            if random.random() < 0.6:
                w = (60 + 340 * min(1, t / 0.5)) * k
                a = x + random.uniform(-w, w)
                self.fx.bolt([(a, y + 2), (a + random.uniform(-90, 90) * k, y + random.uniform(4, 30) * k)],
                             life=0.08, color=random.choice((CYAN, PINK)), width=1.8, jitter=10, branches=1)
                self.fx.sparks(a, y + 3, 2, speed=(100, 400), spread=(20, 160), life=(0.15, 0.3))
            if t > 0.55:
                self.stage = 1
                self._boom()
        elif self.stage == 1 and t > 0.62:  # she falls out of the hole
            self.stage = 2
            self.x, self.y = x, y + 0.2 * self.S
            self.vx, self.vy = random.uniform(-60, 60) * k, 250 * k
            self.intro_only_floor = True
            self.play("dangle")
            self.white = 1.0
            self.body.show()
            self._place()
            self.sfx.play("fall")
            self.set_mode("fall")

    def _boom(self):
        k, x, y = self.k, self.ix, self.iy
        floor = self.screen_rect(x, y + 50).bottom() + 1
        self.sfx.play("boom")
        self.fx.flash(x, y, 340, life=0.45)
        self.fx.flash(x, y, 160, life=0.25, color=PINK)
        self.fx.ring(x, y, 520, life=0.6, color=CYAN, width=4, half=1)
        self.fx.ring(x, y, 330, life=0.5, color=PINK, width=3, half=1, r0=20)
        self.fx.sparks(x, y + 4, 90, speed=(400, 1500), spread=(10, 170), life=(0.25, 0.7), grav=900)
        self.fx.pixels(x, y + 6, 110, self.sp.color, speed=(200, 900), up=(15, 165), ground=floor,
                       life=(2.4, 3.6), size=(3, 8))
        self.fx.glitch_band(x - 700 * k, x + 700 * k, y, y + 120 * k, life=0.7)
        for _ in range(3):  # cracks running along the top of the screen
            d = random.choice((-1, 1)) * random.uniform(150, 420) * k
            self.fx.bolt([(x, y + 2), (x + d, y + random.uniform(2, 24) * k)], life=0.35, width=2.4, jitter=16)

    # -- falling (thrown, dropped, or knocked off a window) -------------------------
    def _fall_step(self, dt):
        g = 2600 * self.k
        self.vy = min(self.vy + g * dt, 4200 * self.k)
        self.vx *= 1 - 0.4 * dt
        nx, ny = self.x + self.vx * dt, self.y + self.vy * dt
        self.white = max(0.0, self.white - dt * 2.5)
        self.angle += (max(-25, min(25, self.vx * 0.02)) - self.angle) * min(1, dt * 6)
        area = self.screen_rect(nx, min(ny, self.y) - 40)
        margin = 0.3 * self.S
        if nx < area.left() + margin:
            nx, self.vx = area.left() + margin, abs(self.vx) * 0.5
        if nx > area.right() - margin:
            nx, self.vx = area.right() - margin, -abs(self.vx) * 0.5
        if ny < area.top() + 1.1 * self.S and self.vy < 0:
            self.vy = max(self.vy, 0) * 0.3
        if self.vy > 0:
            self.refresh_ledges()
            best = None
            for L in self.ledge_list:
                if self.intro_only_floor and L.kind != "floor":
                    continue
                if self.y - 2 <= L.y <= ny + 1 and L.holds(nx) and (best is None or L.y < best.y):
                    best = L
            if best is not None:
                self.x, self.y = nx, best.y
                self.land(best, self.vy)
                return
        self.x, self.y = nx, ny
        if self.vy > 0 and random.random() < 0.25:
            cx, cy = self.center()
            self.fx.embers(cx, cy, 1, radius=40)

    def land(self, L: ledges.Ledge, speed: float):
        self.intro_only_floor = False
        self.seat = L
        self.angle = 0
        self.vx = self.vy = 0
        x = max(L.left + 8, min(L.right - 8, self.x))
        self.x = x
        self.seat_off = (x - L.rect.left(), L.rect.top()) if L.kind == "window" else None
        perch = L.kind != "floor"
        self.set_mode("perch" if perch else "stand")
        self.play("perch_glitch" if perch else "glitch")
        self.impact(speed)
        self.last_touch = self.now
        self.next_roam = self.now + random.uniform(*self.roam)
        if self.say_after:
            line, self.say_after = self.say_after, None
            QTimer.singleShot(650, lambda: self.say(line))
        QTimer.singleShot(700, self._settled)

    def _settled(self):
        cb, self.on_settled = self.on_settled, None
        if cb:
            cb()

    def _land_floor(self, x, y, quiet=False):
        L = next((f for f in ledges.floors() if f.holds(x)), ledges.floors()[0])
        self.x, self.y = x, L.y
        self.body.show()
        if quiet:
            self.seat = L
            self.set_mode("stand")
            self.play("idle")
            self.next_roam = self.now + random.uniform(*self.roam)
        else:
            self.land(L, 0)

    def impact(self, speed):
        """Hit the ground: squash, a splash of her own pixels that bounce and settle, a ground ring."""
        k = self.k
        s = max(0.25, min(1.5, speed / (1900 * k)))
        self.squash_t, self.squash_amt = self.now, 0.12 + 0.16 * min(1, s)
        x, y = self.x + (0.12 * self.S if self.mode == "perch" else 0), self.y
        self.fx.pixels(x, y - 2, int(26 + 70 * s), self.sp.color, speed=(160 * s + 120, 520 * s + 200),
                       up=(195, 345), ground=y, life=(1.3, 2.4), size=(3, 7))
        self.fx.ring(x, y, 70 + 140 * s, life=0.5, color=CYAN, width=3, flat=0.2)
        self.fx.ring(x, y, 40 + 90 * s, life=0.4, color=PINK, width=2.4, flat=0.2)
        self.fx.sparks(x, y - 4, int(12 + 30 * s), speed=(200, 800 * s + 200), spread=(200, 340), life=(0.15, 0.4))
        if s > 0.7:
            self.fx.flash(x, y, 120 * s, life=0.22, color=WHITE)
        self.sfx.play("thud", f"{min(1.0, s):.1f}")
        if s > 0.5:
            QTimer.singleShot(180, lambda: self.sfx.play("tinkle"))

    # -- resting: idle on the floor, or sitting on a window / icon ----------------------
    def _rest_step(self):
        if self.mode == "sleep":
            if self.now - self.st > 40:
                self.wake()
            elif random.random() < 0.012:
                hx, hy = self.head()
                self.fx.embers(hx + 0.1 * self.S, hy + 0.1 * self.S, 1, radius=4, colors=(CYAN,))
            return
        if self.seat and self.seat.kind != "floor":
            self._follow_seat()
            if self.mode != "perch":
                return
        if self.roaming and self.now > self.next_roam and not self.bubble.isVisible() and not self.speaking:
            if random.random() < 0.12:
                self.go_chip()
            else:
                self.teleport()

    def _follow_seat(self):
        """Ride along when her window moves; fall when it closes, minimises or something covers her."""
        L = self.seat
        if L.kind == "window":
            r = ledges.window_rect(L.hwnd)
            if r is not None:
                dx = r.left() - L.rect.left()
                dy = r.top() - L.rect.top()
                if dx or dy:
                    self.x += dx
                    self.y = r.top()
                    L.left += dx
                    L.right += dx
                    L.y = r.top()
                    L.rect = r
        else:
            r = L.rect
        self.refresh_ledges()
        ok = r is not None and any(o.key == L.key and o.holds(self.x) for o in self.ledge_list)
        if ok:
            self.lost_since = -1
            return
        if self.lost_since < 0:
            self.lost_since = self.now
        if self.now - self.lost_since > 0.45:
            self.lost_since = -1
            self.fall_from_here()

    def fall_from_here(self, vx=0.0, vy=0.0):
        self.seat = None
        self.vx, self.vy = vx, vy
        self.play("dangle")
        self.set_mode("fall")

    def wake(self):
        self.play("wake")
        self.set_mode("stand")
        self.next_roam = self.now + random.uniform(*self.roam)

    # -- teleport: charge up, become a bolt of light, strike down somewhere else ---------
    def pick_spot(self):
        self.refresh_ledges(force=True)
        cur = self.seat.key if self.seat else None
        S = self.S
        pools = {"window": [], "icon": [], "floor": []}
        for L in self.ledge_list:
            if L.key == cur and L.kind != "floor":
                continue
            area = self.screen_rect((L.left + L.right) / 2, L.y - 5)
            if L.y - 0.85 * S < area.top():  # no headroom
                continue
            lo, hi = max(L.left, area.left()) + 0.3 * S, min(L.right, area.right()) - 0.45 * S
            if L.kind == "icon":
                lo, hi = L.left + 4, max(L.left + 4, L.right - 4)
            if hi <= lo:
                continue
            pools[L.kind].append((L, lo, hi))
        weights = {"window": 0.45, "icon": 0.25, "floor": 0.3}
        kinds = [k for k in pools if pools[k]]
        if not kinds:
            return None
        kind = random.choices(kinds, [weights[k] for k in kinds])[0]
        L, lo, hi = random.choice(pools[kind])
        for _ in range(6):  # floor: don't land right where she already is
            x = random.uniform(lo, hi)
            if kind != "floor" or abs(x - self.x) > 1.2 * S:
                break
        return L, x

    def teleport(self, spot=None):
        """Defrag: she breaks into her own pixels, they fly over and rebuild her somewhere else."""
        if self.mode not in ("stand", "perch", "sleep"):
            return
        spot = spot or self.pick_spot()
        if not spot:
            self.next_roam = self.now + 5
            return
        self.bubble.close_bubble()
        self.target = spot
        self.play("perch_glitch" if self.mode == "perch" else "glitch")
        self.sfx.play("charge")
        self.set_mode("charge")
        self.last_touch = self.now

    def _charge_step(self):
        t = (self.now - self.st) / 0.42
        e = t * t
        cx, cy = self.center()
        if random.random() < 0.3:
            self.fx.arc_around(cx, cy, 0.42 * self.S, 1, random.choice((CYAN, PINK, WHITE)))
        if random.random() < 0.15:
            self.fx.embers(cx, cy, 1, radius=60)
        self.white = min(0.45, e * 0.5)
        if t >= 1:
            self.white = 0.0
            self.start_stream()

    @staticmethod
    def _pair(src, dst, step):
        """Match pixels top to bottom (her hair flies to where her hair will be), thinned to the same count."""
        n = min(len(src), len(dst))
        if n < 10:
            return None
        src.sort(key=lambda q: (round(q[1] / step), q[0]))
        dst.sort(key=lambda q: (round(q[1] / step), q[0]))

        def even(lst):
            return [lst[round(i * (len(lst) - 1) / max(1, n - 1))] for i in range(n)]

        return even(src), even(dst)

    def _target_pixels(self, L, x, step):
        return self.sp["perch" if L.kind != "floor" else "idle"].sample(0, x, L.y, step)

    def start_stream(self):
        L, x = self.target
        step = 4.0 * self.k
        pair = self._pair(self.sp[self.shown].sample(self.frame, self.x, self.y, step), self._target_pixels(L, x, step), step)
        cx, cy = self.center()
        if not pair:  # nothing to sample (shouldn't happen): just blink over
            self.body.hide()
            self.stream_T = 0.2
            self.seat = None
            return self.set_mode("stream")
        self.body.hide()
        self.sfx.play("stream")
        self.fx.flash(cx, cy, 120, life=0.25, color=PINK)
        self.fx.sparks(cx, cy, 26, speed=(200, 700), life=(0.15, 0.4))
        self.stream_T = self.fx.start_stream(*pair, travel=0.9, spread=0.55)
        self.seat = None
        self.set_mode("stream")

    # -- naps: she streams into her biochip in the corner -----------------------------
    def focus(self):
        """Where a camera should look right now: her, her pixels mid-flight, or her napping sprite."""
        st = self.fx.stream
        if self.mode in ("stream", "to_chip") and st and st["pos"]:
            pos = st["pos"]
            return sum(q[0] for q in pos) / len(pos), sum(q[1] for q in pos) / len(pos)
        if self.mode == "chip":
            fp = self.chip.floor_point()
            return fp.x(), fp.y() - self.chip.side * 0.5
        if self.mode in ("hidden", "intro"):  # not placed yet: watch where she'll come from
            g = ledges.work_area(QGuiApplication.primaryScreen())
            return getattr(self, "ix", g.left() + g.width() * 0.72), g.center().y()
        cx, cy = self.center()
        if self.bubble.isVisible():  # frame her line too: the bubble is wider than she is
            return self.bubble.geometry().center().x(), cy - 0.25 * self.S
        return cx, cy

    def chip_spot(self):
        if self.chip_pos:
            return self.chip_pos
        g = ledges.work_area(QGuiApplication.primaryScreen())
        return g.left() + self.chip.side * 0.62, g.bottom() + 1

    def _chip_moved(self):
        p = self.chip.floor_point()
        self.chip_pos = (p.x(), p.y())

    def go_chip(self, instant=False):
        if self.mode not in ("stand", "perch", "hidden"):
            return
        self.bubble.close_bubble()
        self.seat = None
        cx, cy = self.chip_spot()
        if instant or self.mode == "hidden":
            self.body.hide()
            return self._chip_arrive(quiet=True)
        step = 3.0 * self.k
        pair = self._pair(self.sp[self.shown].sample(self.frame, self.x, self.y, step),
                          sample_chip(self.chip.side, self.dpr, cx, cy, step), step)
        self.body.hide()
        self.sfx.play("stream")
        if pair:
            self.stream_T = self.fx.start_stream(*pair, travel=0.8, spread=0.45)
        else:
            self.stream_T = 0.1
        self.set_mode("to_chip")

    def _chip_arrive(self, quiet=False):
        self.fx.end_stream()
        cx, cy = self.chip_spot()
        self.chip.put(cx, cy)
        self.chip.show()
        self.chip.raise_()
        self.set_mode("chip")
        self.nap_len = random.uniform(50, 110)
        self.snore_at = self.now + 2.5
        if not quiet:
            self.sfx.play("sleep")
            self.fx.flash(cx, cy - self.chip.side * 0.4, 70, life=0.25, color=PINK)
            self.fx.sparks(cx, cy - self.chip.side * 0.4, 12, speed=(100, 300), life=(0.15, 0.35))

    def _chip_step(self):
        self.chip.tick()
        if self.now > self.snore_at:
            self.sfx.play("snore")
            self.snore_at = self.now + 4.5
        if self.roaming and self.now - self.st > self.nap_len:
            self.wake_chip()

    def wake_chip(self, spot=None):
        """Out of the chip: her pixels stream out and rebuild her (next to the chip unless told where)."""
        if self.mode != "chip":
            return
        fp = self.chip.floor_point()
        if spot is None:
            g = ledges.work_area(QGuiApplication.screenAt(fp.toPoint()) or QGuiApplication.primaryScreen())
            x = min(g.right() - 0.5 * self.S, max(g.left() + 0.4 * self.S, fp.x() + 1.3 * self.S))
            L = next((f for f in ledges.floors() if f.holds(x)), ledges.floors()[0])
            spot = (L, x)
        L, x = spot
        step = 3.0 * self.k
        pair = self._pair(sample_chip(self.chip.side, self.dpr, fp.x(), fp.y(), step), self._target_pixels(L, x, step), step)
        self.chip.hide()
        self.sfx.play("wake")
        self.sfx.play("stream")
        self.target = spot
        self.stream_T = self.fx.start_stream(*pair, travel=0.85, spread=0.4) if pair else 0.1
        self.last_touch = self.now
        self.set_mode("stream")

    def arrive(self):
        L, x = self.target
        self.target = None
        k, S = self.k, self.S
        self.x, self.y = x, L.y
        self.seat = L
        self.seat_off = None
        perch = L.kind != "floor"
        self.set_mode("appear")
        self.play("perch_glitch" if perch else "glitch")
        cx, cy = self.center()
        gx = x + (0.12 * S if perch else 0)
        self.sfx.play("rebuild")
        self.fx.end_stream()
        self.fx.flash(cx, cy, 130, life=0.3, color=PINK)
        self.fx.sparks(cx, cy, 30, speed=(150, 600), life=(0.15, 0.4), colors=(PINK, WHITE, CYAN))
        self.white, self.sx, self.sy = 0.8, 1.0, 1.0
        self.fx.flash(gx, L.y, 120, life=0.25, color=PINK)
        self.fx.ring(gx, L.y, 170, life=0.45, color=CYAN, width=3, flat=0.2)
        self.fx.pixels(gx, L.y - 2, 26, self.sp.color, speed=(150, 420), up=(200, 340), ground=L.y, life=(1.0, 1.8), size=(2, 6))
        self._place()
        self.body.show()

    def _appear_step(self):
        t = min(1.0, (self.now - self.st) / 0.38)
        self.white = max(0.0, 0.8 - t * 1.3)
        if t >= 1:
            self.sx = self.sy = 1.0
            self.white = 0
            self.set_mode("perch" if self.seat.kind != "floor" else "stand")
            self.next_roam = self.now + random.uniform(*self.roam)
            if self.roaming and random.random() < 0.2:
                line = random.choice(ARRIVALS)
                if line:
                    QTimer.singleShot(500, lambda: self.say(line))
            self._settled()

    # -- mouse: click to chat, drag to carry, let go to throw ---------------------------
    def press(self, e):
        if e.button() != Qt.LeftButton or self.mode not in ("stand", "perch", "sleep", "fall"):
            return
        self.press_at = e.globalPosition()
        self.grab = e.position()
        self.hist = [(self.now, self.press_at.x(), self.press_at.y())]
        if self.mode == "fall":  # snatch her out of the air
            self._grab()

    def _grab(self):
        self.set_mode("held")
        self.seat = None
        self.play("dangle")
        self.bubble.close_bubble()
        self.white = 0
        self.sx = self.sy = 1.0
        self.sfx.play("grab")

    def drag_move(self, e):
        if self.press_at is None:
            return
        g = e.globalPosition()
        if self.mode != "held":
            if (g - self.press_at).manhattanLength() < 6:
                return
            self._grab()
        self.hist.append((self.now, g.x(), g.y()))
        self.hist = self.hist[-8:]

    def _held_step(self):
        g = QCursor.pos()
        nx = g.x() - self.grab.x() + self.A.x()
        ny = g.y() - self.grab.y() + self.A.y()
        vx = (nx - self.x) * 60
        self.x, self.y = nx, ny
        self.angle += (max(-30, min(30, -vx * 0.012)) - self.angle) * 0.18  # swings behind the motion
        if random.random() < 0.08:
            cx, cy = self.center()
            self.fx.sparks(cx + random.uniform(-30, 30) * self.k, cy + random.uniform(-60, 60) * self.k, 1,
                           speed=(60, 220), life=(0.12, 0.3), grav=300)

    def release(self, e):
        if e.button() != Qt.LeftButton:
            return
        was = self.press_at
        self.press_at = None
        if self.mode != "held":
            if was is not None:
                self.click()
            return
        recent = [h for h in self.hist if self.now - h[0] < 0.09] or self.hist[-2:]
        vx = vy = 0.0
        if len(recent) >= 2 and recent[-1][0] > recent[0][0]:
            span = recent[-1][0] - recent[0][0]
            vx = (recent[-1][1] - recent[0][1]) / span
            vy = (recent[-1][2] - recent[0][2]) / span
        cap = 3200 * self.k
        vx, vy = max(-cap, min(cap, vx)), max(-cap, min(cap, vy))
        self.ledges_at = -9
        if math.hypot(vx, vy) > 900 * self.k:
            cx, cy = self.center()
            self.fx.sparks(cx, cy, 14, speed=(100, 400), life=(0.1, 0.3))
            self.sfx.play("throw")
        self.fall_from_here(vx, vy)
        self.last_touch = self.now

    def click(self):
        self.last_touch = self.now
        self.sfx.play("pop")
        if self.mode == "sleep":
            self.wake()
            return
        if self.bubble.typing:
            self.bubble.close_bubble()
        else:
            hx, hy = self.head()
            self.bubble.open_input()
            self.bubble.place(hx, hy, self.screen_rect(hx, self.y - 10))
        self.next_roam = max(self.next_roam, self.now + 20)

    # -- talking ----------------------------------------------------------------
    def say(self, text, user="", done=None, more=False):
        """Speak a line: the bubble types it in step with her voice, her mouth moves while the audio plays.
        more=True: the reply is still being written; say_more() adds sentences, say_end() closes it (blips only)."""
        if self.mode == "sleep":
            self.wake()
        self.next_roam = max(self.next_roam, self.now + 30)

        def started(secs, cps=None):
            if not self.bubble.isVisible():
                self.sfx.play("pop")
            self.speaking = True
            self.blip_n = 0
            self.bubble.say(text, user=user, secs=secs, cps=cps)

        def ended():
            self.speaking = False
            self.bubble.release(2.4)
            self.next_roam = max(self.next_roam, self.now + 8)
            if done:
                done()

        if self.blips:  # no voice: old-school RPG text blips, paced by the bubble; done once it's all typed
            started(None, 24.0)
            self.talk_open = more
            if self.talk_timer is not None:
                self.talk_timer.stop()
            timer = QTimer()

            def check():
                if not self.talk_open and self.bubble.typed_all():
                    timer.stop()
                    QTimer.singleShot(200, ended)

            timer.timeout.connect(check)
            timer.start(50)
            self.talk_timer = timer
        elif self.voice:
            self.voice(text, started, ended)
        else:
            secs = min(9.0, 0.6 + len(text) * 0.05)
            started(secs)
            QTimer.singleShot(int(secs * 1000), ended)

    def _typed(self, ch: str):
        if self.blips and self.speaking:
            self.blip_n += 1
            if self.blip_n % 2:  # every other letter, like the old handhelds
                self.sfx.play("blip", ch.lower())

    def say_more(self, text: str):
        if self.speaking:
            self.bubble.append(text)
        else:  # the first line already finished: start a fresh one
            self.say(text, more=True)

    def say_end(self):
        self.talk_open = False

    def nap(self):
        self.go_chip()

    def toggle_nap(self):
        if self.mode == "chip":
            self.wake_chip()
        else:
            self.go_chip()

    # -- quitting: a goodbye line, then she switches off like an old CRT --------------------
    def bye(self, then):
        if self.mode == "bye":
            return
        self.roaming = False
        if self.mode == "chip":  # the nap sprite just blinks out
            fp = self.chip.floor_point()
            self.chip.hide()
            self._crt_dot(fp.x(), fp.y() - self.chip.side * 0.45, fp.y())
            QTimer.singleShot(1500, then)
            return
        if self.mode in ("stand", "perch"):
            self.say(random.choice(BYES), done=lambda: self._crt_off(then))
        else:
            self._crt_off(then)

    def _crt_off(self, then):
        self.bubble.close_bubble()
        if not self.body.isVisible():
            QTimer.singleShot(300, then)
            return
        self.play("perch_glitch" if self.mode == "perch" else "glitch")
        self.bye_then = then
        self.sfx.play("crtoff")
        self.set_mode("bye")

    def _bye_step(self):
        t = self.now - self.st
        if t < 0.13:  # squash into a glowing line
            q = t / 0.13
            self.sy, self.sx, self.white = 1 - 0.97 * q, 1 + 0.3 * q, q
        elif t < 0.27:  # the line shrinks to a dot
            q = (t - 0.13) / 0.14
            self.sy, self.sx, self.white = 0.03, 1.3 * (1 - q) + 0.02, 1.0
        else:
            self.body.hide()
            self.sx = self.sy = 1.0
            self.white = 0.0
            cx, cy = self.x, self.y - 0.5 * self.S
            self.set_mode("hidden")
            self._crt_dot(cx, cy, self.y)
            QTimer.singleShot(1500, self.bye_then)

    def _crt_dot(self, x, y, floor):
        """The last glowing pixel hangs for a beat, then drops and bounces on the floor. Bloop."""
        self.fx.flash(x, y, 60, life=0.5)
        self.fx.embers(x, y, 3, radius=3, colors=(WHITE,))
        QTimer.singleShot(450, lambda: (self.fx.parts.append(_dot(x, y, floor, self.k)), self.sfx.play("bloop")))

    def heard(self, line: str):
        self.bubble.think(line)
        self.next_roam = max(self.next_roam, self.now + 40)
        if self.on_user:
            self.on_user(line)
        else:
            QTimer.singleShot(900, lambda: self.say(random.choice(DEMO_REPLIES), user=line))

    # -- menu / tray -------------------------------------------------------------
    def _build_menu(self):
        m = self.menu = QMenu()
        m.setStyleSheet(
            "QMenu { background: rgb(14,6,22); color: rgb(246,240,250); border: 1px solid rgb(255,20,96); padding: 4px; }"
            "QMenu::item { padding: 5px 18px; } QMenu::item:selected { background: rgb(255,20,96); color: black; }"
            "QMenu::separator { height: 1px; background: rgb(60,30,70); margin: 4px 8px; }")
        m.addAction("Jack in  (talk to her)", self.click)
        m.addAction("Defrag  (hop somewhere)", lambda: self.teleport())
        self.nap_action = m.addAction("Go dormant  (nap)", self.toggle_nap)
        m.addAction("Breach the sky  (drop in again)", self.drop_in)
        m.addAction("Ping her", lambda: self.say(random.choice([GREETING] + [a for a in ARRIVALS if a])))
        m.addSeparator()
        roam = QAction("Roam the grid", m, checkable=True, checked=True)
        roam.toggled.connect(lambda on: setattr(self, "roaming", on))
        m.addAction(roam)
        self.roam_action = roam
        m.addSeparator()
        m.addAction("Delta  (quit)", lambda: self.bye(self.quit_fn))
        m.aboutToShow.connect(lambda: self.nap_action.setText("Wake up" if self.mode == "chip" else "Go dormant  (nap)"))

    def _build_tray(self):
        from ..config import ASSETS

        icon = QIcon(str(ASSETS / "icons" / "tray.png"))
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Capri  //  click: nap / wake")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda r: self.toggle_nap() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def _topmost(self):
        import ctypes

        for w in (self.body, self.bubble):
            if w.isVisible():
                ctypes.windll.user32.SetWindowPos(int(w.winId()), -1, 0, 0, 0, 0, 0x2 | 0x1 | 0x10)

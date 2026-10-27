"""Scripted video mode (run.bat video): plays video.txt start to finish and records it.

Before it starts, everything that could hitch is done up front: her lines are pre-voiced (when she has a voice),
the "Capri CMD" window is opened hidden and parked where it will appear, the taskbar is hidden, open windows are
minimised and she's put to sleep in her chip. Press F9 and it records the desktop while the script plays. Every
sound she makes is logged, so the audio track is rebuilt sample-exact afterwards and muxed in: you get
videos/capri_<time>.mp4 (landscape) and capri_<time>_tiktok.mp4 (9:16).
"""
from __future__ import annotations

import atexit
from pathlib import Path
import ctypes
import re
import subprocess
import sys
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from ..config import ROOT
from . import ledges
from . import sfx
from .fx import CYAN, PINK, WHITE

SCRIPT = ROOT / "video.txt"
OUT = ROOT / "videos"
CMD_TITLE = "Capri CMD"
CMD_RECT = (0.07, 0.52, 0.34, 0.30)  # where the CMD pops up: x, y, width, height as fractions of the screen
START_KEY, START_VK = "F9", 0x78
MUSIC = OUT / "music"  # songs for `play:` steps (any audio file: mp3, m4a, wav...)
AUDIO = (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".opus", ".webm", ".aac")


def find_song(arg: str):
    """'I Really Want to Stay at Your House - Rosa Walton | stay.mp3' -> (title, file or None). Without '| file' it
    looks in videos/music for a file named like the song, or the only file there."""
    title, _, file = (x.strip() for x in arg.partition("|"))
    if file:
        for p in (Path(file), ROOT / file, MUSIC / file):
            if p.is_file():
                return title, p
        return title, None
    files = [p for p in MUSIC.glob("*") if p.suffix.lower() in AUDIO] if MUSIC.is_dir() else []
    words = set(re.findall(r"[a-z]{3,}", title.lower()))
    best = max(files, key=lambda p: len(words & set(re.findall(r"[a-z]{3,}", p.stem.lower()))), default=None)
    if best and (words & set(re.findall(r"[a-z]{3,}", best.stem.lower())) or len(files) == 1):
        return title, best
    return title, None


def load_song(path) -> np.ndarray:
    """Any audio file -> mono float32 at the mixer's rate, a bit under her sounds' loudness ceiling."""
    import imageio_ffmpeg

    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-ac", "1", "-ar", str(sfx.SR), "-f", "f32le", "-"], capture_output=True,
                         creationflags=0x08000000).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    peak = float(np.abs(x).max()) if len(x) else 0.0
    return x / peak * 0.5 if peak else x


def beat_pulses(x: np.ndarray, fps: int = 60) -> np.ndarray:
    """The same kick/bass detector as her ear on your speakers, run over the whole song ahead of time:
    one pulse value (0..1) per 1/fps second, so her hair hits exactly on the beats."""
    hop = sfx.SR // fps
    n = len(x) // hop
    if n == 0:
        return np.zeros(1, dtype=np.float32)
    frames = x[: n * hop].reshape(n, hop)
    spec = np.abs(np.fft.rfft(frames * np.hanning(hop), axis=1))
    low = spec[:, 1:max(2, round(300 * hop / sfx.SR))].sum(axis=1)
    out = np.zeros(n, dtype=np.float32)
    avg, pulse, last = float(low[: fps * 2].mean()) or 1e-4, 0.0, -1.0
    for i, v in enumerate(low):
        t = i / fps
        if v > avg * 1.6 and t - last > 0.22:
            pulse, last = 1.0, t
        else:
            pulse *= 0.86 ** (44100 / 1024 / fps)  # same decay per second as the live ear
        avg = avg * 0.96 + v * 0.04
        out[i] = pulse
    return out


def parse(path) -> list[tuple[str, str]]:
    steps = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        verb, _, arg = line.partition(":") if ":" in line.split(" ")[0] else line.partition(" ")
        steps.append((verb.strip().lower(), arg.strip()))
    return steps


# -- Windows bits -------------------------------------------------------------------------------
def taskbar(show: bool) -> None:
    if sys.platform != "win32":
        return
    u = ctypes.windll.user32
    for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        h = u.FindWindowExW(None, None, cls, None)
        while h:
            u.ShowWindow(h, 5 if show else 0)  # SW_SHOW / SW_HIDE
            h = u.FindWindowExW(None, h, cls, None)


def minimize_all() -> None:
    try:
        import win32com.client

        win32com.client.Dispatch("Shell.Application").MinimizeAll()
    except Exception as e:
        print(f"[video] couldn't minimise windows: {e}")


def open_cmd() -> tuple[int, subprocess.Popen | None]:
    """A plain console titled "Capri CMD" with a "capri>" prompt (no user name or PC name anywhere), opened
    hidden. conhost.exe forces the classic console window even when Windows Terminal is the default."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    proc = subprocess.Popen(["conhost.exe", "cmd.exe", "/k", f"title {CMD_TITLE}& prompt capri$G & color 0D& cls"],
                            startupinfo=si, creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=str(ROOT))
    for _ in range(100):
        h = ctypes.windll.user32.FindWindowW("ConsoleWindowClass", CMD_TITLE)
        if h:
            return h, proc
        time.sleep(0.05)
    return 0, proc


def cmd_rect_logical():
    g = QGuiApplication.primaryScreen().geometry()
    fx, fy, fw, fh = CMD_RECT
    return g.x() + g.width() * fx, g.y() + g.height() * fy, g.width() * fw, g.height() * fh


def place_cmd(hwnd: int) -> None:
    d = QGuiApplication.primaryScreen().devicePixelRatio()
    x, y, w, h = (round(v * d) for v in cmd_rect_logical())
    ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0010 | 0x0004)  # NOACTIVATE | NOZORDER


# -- recording ----------------------------------------------------------------------------------
class Recorder:
    """Desktop capture with ffmpeg (gdigrab, NVENC when there is one) + her sound events -> one mp4."""

    def __init__(self, mixer: sfx.Mixer, focus, zoom: float = 1.0):
        self.mixer = mixer
        self.focus = focus  # () -> (x, y) the camera follows in the 9:16 cut
        self.zoom = zoom  # 1 = full screen height; 1.5 = tighter, she fills more of the frame
        self.track: list[tuple[float, float, float]] = []
        self.proc = None
        self.t0 = None
        self.started = threading.Event()

    def start(self) -> bool:
        import imageio_ffmpeg

        self.ff = imageio_ffmpeg.get_ffmpeg_exe()
        OUT.mkdir(exist_ok=True)
        self.name = time.strftime("capri_%Y%m%d_%H%M%S")
        self.raw = OUT / f"{self.name}_raw.mp4"
        for enc in (["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "18"], ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18"]):
            self.t0, self.started = None, threading.Event()
            self.proc = subprocess.Popen(
                [self.ff, "-hide_banner", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0", "-i", "desktop",
                 *enc, "-pix_fmt", "yuv420p", "-y", str(self.raw)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
            threading.Thread(target=self._read, daemon=True).start()
            if self.started.wait(6) and self.proc.poll() is None:
                self.mixer.log = []
                self.cam = QTimer()
                self.cam.timeout.connect(lambda: self.track.append((time.time(), *self.focus())))
                self.cam.start(33)
                print(f"[video] recording ({enc[1]})")
                return True
            self.proc.kill()
        print("[video] couldn't start the screen recorder")
        return False

    def _read(self):
        for line in iter(self.proc.stderr.readline, b""):
            m = re.search(rb"start: ([\d.]+)", line)
            if m and self.t0 is None:
                self.t0 = float(m.group(1))  # wall-clock time of the first frame (gdigrab stamps with it)
                self.started.set()

    def stop(self) -> str | None:
        import soundfile as sf

        end = time.time()
        self.cam.stop()
        events, self.mixer.log = self.mixer.log or [], None
        try:
            self.proc.stdin.write(b"q")
            self.proc.stdin.flush()
        except Exception:
            pass
        self.proc.wait(30)
        wav = OUT / f"{self.name}.wav"
        audio = sfx.render(events, self.t0, end - self.t0 + 0.5)
        fade = min(len(audio), int(sfx.SR * 1.5))  # a song still playing at the end fades out instead of cutting
        audio[len(audio) - fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        sf.write(str(wav), audio, sfx.SR)
        out = OUT / f"{self.name}.mp4"
        subprocess.run([self.ff, "-hide_banner", "-loglevel", "error", "-i", str(self.raw), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-y", str(out)], creationflags=0x08000000)
        # 9:16 for TikTok: a full-height window that pans to follow her (a smoothed camera, so flights whip-pan)
        tiktok = OUT / f"{self.name}_tiktok.mp4"
        cw, ch = self._camera_script(OUT / f"{self.name}_cam.txt")
        vf = f"sendcmd=f={self.name}_cam.txt,crop={cw}:{ch}:0:0,scale=1080:1920:flags=lanczos"
        subprocess.run([self.ff, "-hide_banner", "-loglevel", "error", "-i", out.name, "-vf", vf,
                        "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-c:a", "copy", "-y", tiktok.name],
                       creationflags=0x08000000, cwd=str(OUT))
        (OUT / f"{self.name}_cam.txt").unlink(missing_ok=True)
        if out.exists():
            self.raw.unlink(missing_ok=True)
            wav.unlink(missing_ok=True)
        print(f"[video] saved {out}" + (f" and {tiktok.name}" if tiktok.exists() else ""))
        return str(out) if out.exists() else None


    def _camera_script(self, path) -> tuple[int, int]:
        """sendcmd lines that slide the crop window after her, smoothed like a camera operator would. zoom > 1 crops
        tighter than the full screen height, and then the camera follows her up and down too."""
        scr = QGuiApplication.primaryScreen()
        d, g = scr.devicePixelRatio(), scr.geometry()
        W, H = round(g.width() * d), round(g.height() * d)
        ch = round(H / max(1.0, self.zoom)) // 2 * 2
        cw = round(ch * 9 / 16) // 2 * 2
        pos = vel = None
        lines = []
        w = 7.0  # critically damped spring: quick to catch up, no wobble
        for i, (t, fx, fy) in enumerate(self.track):
            target = (min(max((fx - g.x()) * d - cw / 2, 0), W - cw),
                      min(max((fy - g.y()) * d - ch * 0.5, 0), H - ch))
            if pos is None:
                pos, vel = list(target), [0.0, 0.0]
            dt = t - self.track[i - 1][0] if i else 0.033
            for k in (0, 1):
                vel[k] += (w * w * (target[k] - pos[k]) - 2 * w * vel[k]) * dt
                pos[k] += vel[k] * dt
            x = round(min(max(pos[0], 0), W - cw))
            y = round(min(max(pos[1], 0), H - ch))
            lines.append(f"{max(0.0, t - self.t0):.3f} crop x {x}, crop y {y};")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return cw, ch


class _Signals(QObject):
    armed = Signal()


class Video:
    def __init__(self, desk, autostart: bool = False, script=None):
        self.desk, self.capri = desk, desk.capri
        self.autostart = autostart
        self.capri.roaming = False
        if self.capri.roam_action:
            self.capri.roam_action.setChecked(False)
        ledges.FULL = True
        self.steps = parse(Path(script) if script else SCRIPT)
        self.zoom = next((float(a) for v, a in self.steps if v == "zoom"), 1.0)  # a setting, not a step
        self.steps = [(v, a) for v, a in self.steps if v != "zoom"]
        if self.zoom > 1:  # the tight 9:16 frame is narrow: her bubble wraps to fit inside it instead of getting cut off
            g = QGuiApplication.primaryScreen().geometry()
            frame_w = g.height() / self.zoom * 9 / 16
            b = self.capri.bubble
            b.inner_w = min(b.inner_w, frame_w * 0.9 - 2 * b.pad - 12 * b.s)
        self.i = 0
        self.you = ""  # your last line: her next `say` shows it above her reply, like a real chat
        self.songs: dict[str, tuple] = {}  # play: arg -> (title, samples, pulses), loaded in _prepare
        self.cmd, self.cmd_proc = 0, None
        self.rec = None
        self.sig = _Signals()
        self.sig.armed.connect(self._armed)
        desk.on_quit.append(self._cleanup)
        atexit.register(taskbar, True)
        threading.Thread(target=self._prepare, daemon=True).start()

    def _cleanup(self):
        taskbar(True)
        if self.cmd_proc and self.autostart:
            self.cmd_proc.kill()

    # -- getting ready (off camera) ---------------------------------------------------------
    def _prepare(self):
        if any(v == "cmd" for v, _ in self.steps):
            self.cmd, self.cmd_proc = open_cmd()
            print(f"[video] Capri CMD ready ({'found' if self.cmd else 'NOT found'})")
        for arg in {a for v, a in self.steps if v == "play"}:
            title, path = find_song(arg)
            if path is None:
                print(f"[video] no audio file for {title!r}: put it in {MUSIC} (that part of the video will be silent)")
                self.songs[arg] = (title, None, None)
                continue
            x = load_song(path)
            sfx.add_track(arg, x)
            self.songs[arg] = (title, x, beat_pulses(x))
            print(f"[video] song ready: {path.name} ({len(x) / sfx.SR:.0f}s)")
        if not self.capri.blips:
            tts = self.desk.tts
            lines = [a for v, a in self.steps if v == "say"]
            t0 = time.time()
            while not tts.ready() and time.time() - t0 < 300:
                print("[video] waiting for her voice to load ...")
                time.sleep(3)
            for n, text in enumerate(lines, 1):
                try:
                    tts.prepare(text)
                    print(f"[video] voiced {n}/{len(lines)}: {text}")
                except Exception as e:
                    print(f"[video] couldn't pre-voice {text!r}: {e}")
        self.sig.armed.emit()

    def _armed(self):
        if self.cmd:
            place_cmd(self.cmd)
        minimize_all()
        taskbar(False)
        if self.steps and self.steps[0][0] == "chip":  # opening shot: already napping in her chip
            self.i = 1
            self.capri.go_chip(instant=True)
        if self.autostart:
            QTimer.singleShot(1500, self._start)
            return
        print(f"[video] READY. Press {START_KEY} to record (it stops by itself at the end).")
        ctypes.windll.user32.GetAsyncKeyState(START_VK)  # forget any F9 pressed before now
        self.key_timer = QTimer()
        self.key_timer.timeout.connect(self._poll_key)
        self.key_timer.start(40)

    def _poll_key(self):
        """F9 anywhere (no keyboard hook needed: just ask Windows whether it went down)."""
        if ctypes.windll.user32.GetAsyncKeyState(START_VK) & 0x8001:
            self.key_timer.stop()
            self._start()

    # -- the show ---------------------------------------------------------------------------
    def _start(self):
        self.rec = Recorder(self.capri.sfx, lambda: self.capri.focus(), self.zoom)
        if not self.rec.start():
            self.rec = None
        print("[video] action!")
        QTimer.singleShot(1000, self._next)  # a beat of empty desktop before anything happens

    def _next(self, gap: float = 0.0):
        if gap:
            QTimer.singleShot(int(gap * 1000), self._next)
            return
        if self.i >= len(self.steps):
            return self._wrap()
        verb, arg = self.steps[self.i]
        self.i += 1
        c = self.capri
        if verb == "wait":
            self._next(float(arg or 1))
        elif verb == "chip":
            c.on_settled = None
            c.go_chip()
            self._next(1.6)
        elif verb == "wake":
            c.on_settled = lambda: self._next(0.3)
            g = ledges.work_area(QGuiApplication.primaryScreen())
            x = g.left() + g.width() * float(arg or 0.7)
            c.wake_chip((next(f for f in ledges.floors() if f.holds(x)), x))
        elif verb == "drop":
            c.on_settled = lambda: self._next(0.4)
            c.drop_in(greet=False, x_frac=0.72)
        elif verb == "say":
            c.say(arg, user=self.you, done=lambda: self._next(0.45))
            self.you = ""
        elif verb == "type":
            self._type(arg)
        elif verb == "you":
            self._voice(arg)
        elif verb == "play":
            self._play(arg)
            self._next(0.3)
        elif verb == "cmd":
            self._summon_cmd()
            self._next(0.5)
        elif verb in ("defrag", "zap"):
            c.on_settled = lambda: self._next(0.3)
            c.teleport(self._cmd_spot())
        else:
            print(f"[video] unknown step {verb!r}, skipped")
            self._next()

    def _type(self, line: str):
        """You typing to her: her type box opens and the line goes in key by key, then it's sent."""
        b = self.capri.bubble
        b.open_input()
        b.edit.clear()
        self.capri.sfx.play("pop")
        rng = np.random.default_rng(len(line))
        n = [0]

        def key():
            if n[0] < len(line):
                n[0] += 1
                b.edit.setText(line[:n[0]])
                self.capri.sfx.play("key")
                ch = line[n[0] - 1]
                gap = 0.06 + rng.random() * 0.07 + (0.12 if ch in " ,." else 0)  # human-ish rhythm
                QTimer.singleShot(int(gap * 1000), key)
            else:
                QTimer.singleShot(450, send)

        def send():
            b.edit.clear()
            b.typing = False
            b.edit.hide()
            b.nap_btn.hide()
            b.think(line)  # "> your line" with her "..." under it, until she answers
            self.you = line
            self._next(0.9)

        QTimer.singleShot(350, key)

    def _voice(self, line: str):
        """You talking to her: the listening bubble with your mic level moving, then your words appear."""
        c, b = self.capri, self.capri.bubble
        c.listening(True)
        secs = 0.8 + len(line) * 0.055
        t0 = time.monotonic()
        rng = np.random.default_rng(len(line))
        meter = QTimer()

        def tick():
            t = time.monotonic() - t0
            if t < secs:
                b.mic_level = float(0.25 + 0.6 * rng.random()) * min(1.0, t * 4)
                return
            meter.stop()
            b.mic_level = 0.0
            c.listening(False)
            b.think(line)
            self.you = line
            self._next(0.9)

        meter.timeout.connect(tick)
        meter.start(60)
        self._meter = meter

    def _play(self, arg: str):
        """She puts the song on: it plays through your speakers (and into the recording) and her hair glitches to
        its beat, worked out from the song itself."""
        title, x, pulses = self.songs.get(arg, (arg, None, None))
        at = time.time() - (self.rec.t0 if self.rec and self.rec.t0 else time.time())
        print(f"[video] {title} starts at {at:.1f}s into the video")
        if x is None:
            return
        c = self.capri
        start = time.monotonic()
        end = start + len(x) / sfx.SR

        def beat():
            now = time.monotonic()
            if now >= end:
                return 0.0, False
            return float(pulses[min(len(pulses) - 1, int((now - start) * 60))]), True

        c.beat = beat
        c.sfx.quiet = lambda: time.monotonic() < end  # her blips go a little softer under the song
        with c.sfx.lock:  # straight in: play() would drop it if something already counted as music
            c.sfx.voices.append([sfx.sound("song", arg), 0])
            if c.sfx.log is not None:
                c.sfx.log.append((time.time(), "song", arg))

    def _wrap(self):
        print("[video] that's a wrap")

        def finish():
            if self.rec:
                print("[video] saving the video ...")
                self.rec.stop()
            taskbar(True)
            if self.autostart:
                self.desk.quit()
            print("[video] done. Quit from the tray icon whenever.")

        QTimer.singleShot(1800, finish)

    def _summon_cmd(self):
        """The console glitches into existence: a tear across where it'll be, a flash, a coin ding, then it flickers on."""
        if not self.cmd:
            return
        x0, y0, w, h = cmd_rect_logical()
        fx = self.capri.fx
        fx.glitch_band(x0 - 40, x0 + w + 40, y0, y0 + h, life=0.45)
        fx.flash(x0 + w / 2, y0 + h / 2, 220, life=0.3, color=PINK)
        fx.ring(x0 + w / 2, y0 + h / 2, 260, life=0.45, color=CYAN, width=2.5)
        for _ in range(3):
            fx.arc_around(x0 + w / 2, y0 + h / 2, 160, 1, CYAN)
        fx.sparks(x0 + w / 2, y0, 30, speed=(200, 700), spread=(180, 360), life=(0.2, 0.45), colors=(CYAN, WHITE, PINK))
        self.capri.sfx.play("coin")
        real = self.capri.focus
        self.capri.focus = lambda: (x0 + w * 0.3, y0 + h / 2)
        QTimer.singleShot(1300, lambda: setattr(self.capri, "focus", real))
        u = ctypes.windll.user32
        for ms, show in ((60, True), (120, False), (190, True), (240, False), (300, True)):
            QTimer.singleShot(ms, lambda s=show: u.ShowWindow(self.cmd, 4 if s else 0))  # SW_SHOWNOACTIVATE / HIDE

    def _cmd_spot(self):
        c = self.capri
        c.refresh_ledges(force=True)
        for L in c.ledge_list:
            if L.kind == "window" and L.hwnd == self.cmd:
                return L, L.left + (L.right - L.left) * 0.32
        return None  # no CMD: anywhere new

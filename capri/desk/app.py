"""Wires Capri on the desktop to her brain (Mistral-Nemo + memory), ears (faster-whisper), eyes (window + OCR),
music (YouTube DJ + a beat ear on your speakers) and voice."""
from __future__ import annotations

import os
import random
import re
import sys
import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication
from PySide6.QtWidgets import QApplication

from .. import config
from ..voice import tts as tts_mod
from .capri import Capri
from .settings import Settings


class Bridge(QObject):
    """Thread-safe hop from worker threads (brain, ears, voice) back onto the Qt thread."""

    replied = Signal(str, str, bool)  # her text, what the user said ("" = her own idea), go nap afterwards
    part = Signal(str, str, bool)  # one sentence of a reply still being written, what the user said, first sentence?
    part_end = Signal(bool)  # that reply is finished (go nap afterwards?)
    started = Signal(object, float)  # line token, seconds of audio
    ended = Signal(object)
    heard = Signal(str)
    hearing = Signal(bool)
    level = Signal(float)


def idle_seconds() -> float:
    """Seconds since the last keyboard / mouse input anywhere on Windows."""
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    li = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


class DeskApp:
    def __init__(self, video: bool = False):
        self.cfg = config.load()
        d = self.cfg["desk"]
        self.video_mode = video
        self.s = Settings(self.cfg)
        self.bridge = Bridge()
        size = int(d["video_size"] if video else d["size"])  # bigger for the camera
        # stream mode only when stream.bat starts her (--stream): the normal launch is always her desktop self.
        # On the stream, her CMD boots her on the Capri Stage instead of the desktop.
        self.dev = self.cfg.get("edition") == "dev"  # the portable test build for other devs
        self.streaming = "--stream" in sys.argv and not self.dev
        self.capri = Capri(size, tuple(d["roam_seconds"]), intro=bool(d["intro"]) and not video and not self.streaming,
                           start=not video)
        self.capri.voice = self.voice
        self.capri.blips = self.cfg["tts"]["backend"] == "blips"
        self.capri.on_user = self.on_user
        self.capri.quit_fn = self.quit
        self.on_quit: list = []
        self.lines: dict[object, tuple] = {}
        b = self.bridge
        b.replied.connect(self._replied)
        b.part.connect(self._part)
        b.part_end.connect(self._part_end)
        self.nap_after = False
        b.started.connect(lambda tok, secs: self.lines[tok][0](secs) if tok in self.lines else None)
        b.ended.connect(self._ended)
        b.heard.connect(self.capri.heard)
        b.hearing.connect(self._hearing)
        b.level.connect(lambda v: setattr(self.capri.bubble, "mic_level", v))
        self.agent = None
        self.busy = threading.Lock()
        self.tts = tts_mod.create(self.cfg)
        self.ears = None
        self.beat = None
        if video:  # the video is scripted: no brain, ears or eyes needed
            return
        threading.Thread(target=self._boot, daemon=True).start()
        self._start_ears()
        QTimer.singleShot(5000, self._start_beat)  # after boot: starting it mid-startup raced numpy imports and crashed
        self.stream = None
        if not self.dev:
            from .stream import Stream

            self.stream = Stream(self)
        self._build_menu()
        if self.streaming:
            QTimer.singleShot(600, lambda: self.stream.set(True))
        # what she keeps an eye on
        self.title = ""
        self.last_own = time.monotonic()  # last time she said something unprompted
        self.last_talk = time.monotonic()  # last time you two talked
        self.idle_pinged = False
        self.song = ""  # YouTube song in the browser
        self.song_since = 0.0
        self.song_judged = ""
        self.her_pick = ""  # what she put on (DJ mode), so she doesn't judge her own pick
        self.last_glance = 0.0
        from ..abilities.music import Playlist

        self.playlist = Playlist()
        self.watch = QTimer()
        self.watch.timeout.connect(self._watch)
        self.watch.start(3000)

    # -- boot ---------------------------------------------------------------------
    def _boot(self):
        from ..brain.agent import Agent

        t = time.monotonic()
        # picked from her Brain menu, one for talking with you and one for streams (where speed matters more)
        brain = (self.s["stream_brain"] if self.streaming else "") or self.s["brain"]
        if brain:
            self.cfg["llm"]["model_path"] = brain
        self.agent = Agent(self.cfg)
        self.agent.on_played = self._played
        from ..abilities.launcher import warm_youtube

        threading.Thread(target=warm_youtube, daemon=True).start()
        try:
            self.agent.warm_up()
        except Exception as e:
            print(f"[capri] warm-up failed: {e}")
        print(f"[capri] brain online in {time.monotonic() - t:.1f}s")
        sight_dir = None if self.dev else self.cfg.get("sight", {}).get("model_dir")
        if sight_dir and self.streaming:  # streaming: TikTok LIVE Studio and VTube Studio need that GPU memory
            print("[capri] stream mode: her eyes (InternVL) stay off to save ~2.6 GB of GPU memory")
            sight_dir = None
        if sight_dir:  # her real eyes load after the brain, so they only take what VRAM is left
            from ..abilities.sight import Eyes
            from ..brain.llm import GPU_LOCK

            for _ in range(120):  # the ears import the same libraries: loading both at once broke transformers' imports
                if self.ears is None or self.ears.stt is not None or not self.ears.is_alive():
                    break
                time.sleep(0.5)
            eyes = Eyes(sight_dir, GPU_LOCK)
            eyes.load()
            if not eyes.ok and "ImportError" in (eyes.error or ""):
                time.sleep(3)
                eyes = Eyes(sight_dir, GPU_LOCK)
                eyes.load()
            self.agent.eyes = eyes

    def _played(self, result: str):
        if result.startswith("playing"):
            self.her_pick = result[len("playing "):].rsplit(" on YouTube", 1)[0]

    def _start_ears(self):
        try:
            from ..voice.stt import Listener

            if self.s["whisper_model"]:
                self.cfg["stt"]["whisper_model"] = self.s["whisper_model"]
            self.ears = Listener(self.cfg, self.s, self.bridge.heard.emit, self.bridge.hearing.emit, self.bridge.level.emit)
            self.ears.start()
        except Exception as e:
            print(f"[capri] ears unavailable: {e}")

    def _start_beat(self):
        try:
            from ..abilities.music import BeatEar

            self.beat = BeatEar()
            self.beat.start()
            # music = a YouTube song in the browser, or a steady beat (not game explosions)
            music = lambda: self.beat.playing and (bool(getattr(self, "song", "")) or self.beat.rhythmic)  # noqa: E731
            self.capri.beat = lambda: (self.beat.pulse, music()) if self.s["vibe"] else (0.0, False)
            self.capri.sfx.quiet = music  # no booms or zaps over your songs
        except Exception as e:
            print(f"[capri] beat ear unavailable: {e}")

    def _hearing(self, on: bool):
        self.capri.listening(on)
        if on:
            self.last_talk = time.monotonic()

    # -- voice --------------------------------------------------------------------
    def voice(self, text, on_start, on_end):
        tok = object()
        self.lines[tok] = (on_start, on_end)
        tts_mod.speak_async(self.tts, text, lambda secs: self.bridge.started.emit(tok, secs),
                            lambda: self.bridge.ended.emit(tok))

    def _ended(self, tok):
        cbs = self.lines.pop(tok, None)
        if cbs:
            cbs[1]()

    # -- brain --------------------------------------------------------------------
    def on_user(self, line: str):
        self.last_talk = time.monotonic()
        if self.agent is None:
            self.capri.say("Hold up, choom, my brain's still booting. Gimme a sec.", user=line)
            return
        if not self.busy.acquire(blocking=False):
            return
        print(f"[capri] you: {line}")

        def work():
            t = time.monotonic()
            try:
                first = [True]

                def sentence(s):
                    if first[0]:
                        print(f"[capri] first words after {time.monotonic() - t:.2f}s")
                    self.bridge.part.emit(s, line, first[0])
                    first[0] = False

                streaming = self.capri.blips  # a real voice needs the whole line before it can speak
                reply = self.agent.respond(line, on_sentence=sentence if streaming else None)
                for a in reply.actions:
                    print(f"[capri] {a}")
                print(f"[capri] capri ({time.monotonic() - t:.1f}s): {reply.text}")
                if streaming and not first[0]:
                    self.bridge.part_end.emit(reply.go_idle)
                else:
                    self.bridge.replied.emit(reply.text, line, reply.go_idle)
                threading.Thread(target=self.agent.learn, args=(line,), daemon=True).start()
            except Exception as e:
                import traceback

                traceback.print_exc()
                self.bridge.replied.emit(f"Something flatlined in my code: {e}", line, False)
            finally:
                self.busy.release()

        threading.Thread(target=work, daemon=True).start()

    def _replied(self, text: str, line: str, nap: bool):
        if self.ears:
            self.ears.muted = True  # auto mode: don't transcribe her own blips

        def done():
            if self.ears:
                self.ears.muted = False
            if nap:
                self.capri.nap()

        self.capri.say(text, user=line, done=done)

    def _part(self, text: str, line: str, first: bool):
        if not first:
            self.capri.say_more(text)
            return
        if self.ears:
            self.ears.muted = True
        self.nap_after = False

        def done():
            if self.ears:
                self.ears.muted = False
            if self.nap_after:
                self.capri.nap()

        self.capri.say(text, user=line, done=done, more=True)

    def _part_end(self, nap: bool):
        self.nap_after = nap
        self.capri.say_end()

    def _own(self, make, then=None):
        """Something she brings up herself: think in the background, say it if it's still a good moment."""
        if self.agent is None or self.capri.mode not in ("stand", "perch") or self.capri.speaking or self.capri.bubble.isVisible():
            return
        if not self.busy.acquire(blocking=False):
            return
        self.last_own = time.monotonic()

        def work():
            try:
                text = make()
                if text:
                    print(f"[capri] capri (own): {text}")
                    self.bridge.replied.emit(text, "", False)
                if then:
                    then()
            except Exception as e:
                print(f"[capri] own line failed: {e}")
            finally:
                self.busy.release()

        threading.Thread(target=work, daemon=True).start()

    # -- eyes, chatter and the DJ (every 3 s) --------------------------------------------------
    def _watch(self):
        from ..abilities import vision
        from ..abilities.music import CYBER

        if self.agent is None:
            return
        d = self.cfg["desk"]
        now = time.monotonic()
        cooldown = d["react_cooldown_minutes"] * 60
        idle = idle_seconds()

        # what's playing on YouTube (any window, even behind others)
        song = vision.youtube_song(vision.window_titles())
        self.agent.now_playing = song
        if song != self.song:
            self.song, self.song_since = song, now
        playing = song and (self.beat is None or self.beat.playing)

        # her eyes: a fresh glance when you switch windows (and every 30 s anyway)
        title = vision.active_window_title().strip()
        own_window = not title or title in ("Capri", "Capri CMD") or "Program Manager" in title
        switched = title != self.title and not own_window
        if switched:
            self.title = title
        if self.s["eyes"] and not own_window and (switched or now - self.last_glance > 30):
            self.last_glance = now

            def look():
                t, text = vision.glance()
                self.agent.glance = {"t": time.time(), "title": t, "text": text}

            threading.Thread(target=look, daemon=True).start()

        # DJ: judge a new song once it's been on a bit
        if playing and song != self.song_judged and now - self.song_since > 12:
            self.song_judged = song
            mine = self.her_pick and _same_song(self.her_pick, song)
            if mine:
                if random.random() < 0.6:
                    self._own(lambda: self.agent.hype_line(song))
                return
            if self.s["dj"] and not self.dev and not CYBER.search(song):
                pick = self.playlist.next()

                def swap():
                    from ..abilities import launcher
                    from ..abilities.spotify import _media_key

                    _media_key("pause")
                    time.sleep(0.4)
                    result = launcher.youtube_play(pick)
                    print(f"[capri] DJ: {result}")
                    if result.startswith("playing"):
                        self.her_pick = result[len("playing "):].rsplit(" on YouTube", 1)[0]

                self._own(lambda: self.agent.music_take(song, switching_to=pick.split(" (")[0]), then=swap)
                return
            if now - self.last_own > cooldown and random.random() < 0.5:
                self._own(lambda: self.agent.music_take(song))
                return

        if not self.s["chatter"]:
            return
        # you've been gone a while
        if idle > d["chatter_idle_minutes"] * 60:
            if not self.idle_pinged and now - self.last_own > cooldown:
                self.idle_pinged = True
                self._own(lambda: self.agent.idle_line(int(idle // 60)))
            return
        self.idle_pinged = False
        # you just opened something new
        if switched and now - self.last_own > cooldown and now - self.last_talk > 60 and random.random() < 0.5:
            QTimer.singleShot(2500, lambda: self._own(lambda: self.agent.react_line(title)))  # after the glance lands

    # -- menu ---------------------------------------------------------------------
    def _build_menu(self):
        from ..voice import hotkey

        self._hotkey = hotkey
        m = self.capri.menu
        before = m.actions()[-1]  # keep "Delta (quit)" last
        ears = m.addMenu("Ears")
        m.insertMenu(before, ears)
        group = QActionGroup(ears)
        self.ear_actions = {}
        for mode, label in (("hold", "Hold to talk"), ("auto", "Auto (always listening)"), ("off", "Off")):
            a = QAction(label, ears, checkable=True, checked=self.s["ears"] == mode)
            a.triggered.connect(lambda _=False, md=mode: self.s.set("ears", md))
            group.addAction(a)
            ears.addAction(a)
            self.ear_actions[mode] = a
        ears.addSeparator()
        self.key_action = ears.addAction("Change talk key", self._rebind)
        mics = ears.addMenu("Mic")
        ears.aboutToShow.connect(lambda: self._fill_ears(mics))
        if self.dev:  # her whisper model, picked in setup; switching restarts her ears
            self._ear_models = ears.addMenu("Model")
            ears.aboutToShow.connect(self._fill_ear_models)
        toggles = (("dj", "Let her DJ (Cyberpunk OSTs)"), ("vibe", "Vibe to the music"),
                   ("eyes", "Watch my screen"), ("chatter", "Chatter / react  (she talks on her own)"))
        for key, label in toggles[1:] if self.dev else toggles:
            a = QAction(label, m, checkable=True, checked=bool(self.s[key]))
            a.toggled.connect(lambda on, k=key: self.s.set(k, on))
            m.insertAction(before, a)
        m.insertSeparator(before)
        brains = m.addMenu("Brain")
        m.insertMenu(before, brains)
        brains.aboutToShow.connect(lambda: self._fill_brains(brains))
        if not self.dev:
            live = QAction("Stream mode  (Capri Stage for TikTok LIVE)", m, checkable=True, checked=self.streaming)
            live.toggled.connect(lambda on: (setattr(self, "streaming", on), self.stream.set(on)))  # just this run
            m.insertAction(before, live)
        m.insertSeparator(before)

    def _fill_brains(self, menu):
        """Every .gguf in ERU AI's models/llm folder; picking one swaps her brain live (a few seconds)."""
        import glob

        menu.clear()
        cur = os.path.normcase(os.path.abspath(self.cfg["llm"].get("model_path") or ""))
        if self.dev:
            from .. import portable

            paths = [str(p) for p in portable.brains()]
        else:
            root = os.path.join(self.cfg["eru_ai_root"], "models", "llm")
            paths = sorted(glob.glob(os.path.join(root, "**", "*.gguf"), recursive=True))
        for path in paths:
            if "mmproj" in os.path.basename(path).lower():  # a vision add-on file, not a brain
                continue
            name = os.path.basename(path).rsplit(".", 1)[0]
            label = re.sub(r"[-_.](?:Q\d\w*|IQ\d\w*|q\d\w*)$", "", name)
            a = menu.addAction(f"{label}  ({os.path.getsize(path) / 2 ** 30:.1f} GB)")
            a.setCheckable(True)
            a.setChecked(os.path.normcase(os.path.abspath(path)) == cur)
            a.triggered.connect(lambda _=False, p=path: self._swap_brain(p))
        if self.dev:
            from .. import portable

            menu.addSeparator()
            menu.addAction("Add your own model...  (drop a .gguf in this folder)",
                           lambda: (portable.LLM_DIR.mkdir(parents=True, exist_ok=True), os.startfile(portable.LLM_DIR)))
            menu.addAction("Download more models / ears...", self._open_setup)

    def _fill_ear_models(self):
        from .. import portable

        menu = self._ear_models
        menu.clear()
        cur = self.s["whisper_model"] or ""
        for path in portable.ears_models():
            a = menu.addAction(path.name.replace("ggml-", "").replace(".bin", ""))
            a.setCheckable(True)
            a.setChecked(path.name == cur or (not cur and "small" in path.name))
            a.triggered.connect(lambda _=False, n=path.name: self._swap_ears(n))

    def _swap_ears(self, name: str):
        """A different whisper model: saved, and her ears restart with it."""
        self.s.set("whisper_model", name)
        self.cfg["stt"]["whisper_model"] = name
        if self.ears:
            self.ears.stopped = True
            stt = getattr(self.ears, "stt", None)
            if stt is not None and hasattr(stt, "close"):
                stt.close()
        QTimer.singleShot(1500, self._start_ears)

    def _open_setup(self):
        """The download window again (her Brain menu), to add models; she keeps running meanwhile."""
        from ..setup import SetupWindow

        self._setup = SetupWindow(first_run=False)
        self._setup.show()

    def _swap_brain(self, path: str):
        if self.agent is None or os.path.normcase(path) == os.path.normcase(self.cfg["llm"].get("model_path") or ""):
            return
        self.s.set("stream_brain" if self.streaming else "brain", path)
        self.capri.say("Hold up, swapping out my brain chip. Don't look.")

        def work():
            import gc

            from ..brain import llm as llm_mod

            with self.busy:  # nothing else thinks while the brain is out
                t = time.monotonic()
                with llm_mod.GPU_LOCK:
                    old = self.agent.llm
                    self.agent.llm = None
                    try:
                        old.model.close()
                    except Exception:
                        pass
                    del old
                    gc.collect()
                self.cfg["llm"]["model_path"] = path
                try:
                    self.agent.llm = llm_mod.create(self.cfg)
                    self.agent.warm_up()
                    print(f"[capri] brain swapped to {os.path.basename(path)} in {time.monotonic() - t:.1f}s")
                    self.bridge.replied.emit("New brain chip, who dis? ...Okay, I'm back.", "", False)
                except Exception as e:
                    print(f"[capri] brain swap failed: {e}")
                    self.bridge.replied.emit(f"That brain chip flatlined: {e}", "", False)

        threading.Thread(target=work, daemon=True).start()

    def _fill_ears(self, mics):
        self.key_action.setText(f"Change talk key  (now {self._hotkey.pretty(self.s['talk_key'])})")
        mics.clear()
        from ..voice.stt import list_inputs

        cur = self.s["mic"] or self.cfg["stt"].get("input_device") or ""
        for name in ["Windows default"] + list_inputs():
            a = mics.addAction(name)
            a.setCheckable(True)
            a.setChecked((name == "Windows default" and not cur) or (bool(cur) and cur.lower() in name.lower()))
            a.triggered.connect(lambda _=False, n=name: self._pick_mic("" if n == "Windows default" else n))

    def _pick_mic(self, name: str):
        self.s.set("mic", name)
        if self.ears:
            self.ears.reopen = True

    def _rebind(self):
        """Ask for the new combo, then catch it as soon as every key is let go."""
        self.capri.say("Hit your new talk key combo, choom. I'm watching.")
        cap = self._hotkey.Capture()
        timer = QTimer()
        started = time.monotonic()

        def poll():
            if time.monotonic() - started < 0.6:  # let go of the menu click first
                return
            combo = cap.poll()
            if combo:
                timer.stop()
                self.s.set("talk_key", combo)
                self.s.set("ears", "hold")
                self.ear_actions["hold"].setChecked(True)
                self.capri.say(f"Locked in. Hold {self._hotkey.pretty(combo)} and talk to me.")
            elif time.monotonic() - started > 12:
                timer.stop()
                self.capri.say("Too slow, choom. Keeping the old key.")

        timer.timeout.connect(poll)
        timer.start(20)
        self._rebind_timer = timer

    def quit(self):
        """Stop the voice server, then leave without the interpreter's teardown (CUDA + PortAudio threads
        being torn down at exit crash on Windows)."""
        for hook in self.on_quit:
            try:
                hook()
            except Exception as e:
                print(f"[capri] quit hook failed: {e}")
        if self.ears:
            self.ears.stopped = True
        # the portable build's helper servers (llama-server, whisper-server) go with her
        for helper in (getattr(self.agent, "llm", None), getattr(self.ears, "stt", None)):
            if helper is not None and hasattr(helper, "close"):
                try:
                    helper.close()
                except Exception:
                    pass
        proc = getattr(self.tts, "proc", None)
        if proc:
            proc.terminate()
        sys.stdout.flush()
        os._exit(0)


def _same_song(a: str, b: str) -> bool:
    words = lambda s: set(re.findall(r"[a-z0-9']{3,}", s.lower()))  # noqa: E731
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) > 0.6


def main():
    import argparse

    ap = argparse.ArgumentParser(prog="capri")
    ap.add_argument("--video", action="store_true", help="play and record the scripted video (video.txt)")
    ap.add_argument("--autostart", action="store_true", help="video: start recording as soon as it's ready, quit when done")
    ap.add_argument("--script", help="video: which script to play (default video.txt)")
    ap.add_argument("--stream", action="store_true", help="stream mode for this run: Capri Stage for TikTok LIVE")
    args = ap.parse_args()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    desk = DeskApp(video=args.video)
    if args.video:
        from .video import Video

        desk.video = Video(desk, autostart=args.autostart, script=args.script)
    sys.exit(app.exec())

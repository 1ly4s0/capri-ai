"""Music: her Cyberpunk playlist for DJ mode, and an ear on your speakers so she can vibe to the beat.

The beat ear listens to what the PC is playing (WASAPI loopback through the `soundcard` package), finds kicks
in the low end, and exposes `pulse` (jumps to 1 on a beat, then decays) and `playing` (music has been going a
couple of seconds)."""
from __future__ import annotations

import random
import re
import threading
import time
import warnings

import numpy as np

# Cyberpunk 2077 and Edgerunners: what she reaches for when your music isn't nova enough
OSTS = [
    "I Really Want to Stay at Your House - Rosa Walton & Hallie Coggins",
    "This Fffire - Franz Ferdinand (Cyberpunk Edgerunners opening)",
    "Let You Down - Dawid Podsiadlo (Cyberpunk Edgerunners)",
    "Never Fade Away - SAMURAI (Olga Jankowska)",
    "Chippin' In - SAMURAI",
    "Black Dog - SAMURAI",
    "The Rebel Path - P.T. Adamczyk Cyberpunk 2077",
    "Resist and Disorder - Rezodrone Cyberpunk 2077",
    "Major Crimes - HEALTH Cyberpunk 2077",
    "Night City - R E L & Artemis Delta",
    "Delicate Weapon - Lizzy Wizzy Cyberpunk 2077",
    "PonPon Shit - Us Cracks Cyberpunk 2077",
    "Who's Ready for Tomorrow - Rat Boy & IBDY",
]

# a YouTube title that's already Night City music: she approves instead of switching it
CYBER = re.compile(r"cyberpunk|edgerunners|samurai|night city|rosa walton|p\.?\s*t\.?\s*adamczyk|rezodrone|lizzy wizzy|"
                   r"franz ferdinand.*fffire|dawid podsiad|health.*major crimes|us cracks|rat boy|kavinsky|perturbator|"
                   r"carpenter brut|synthwave|retrowave|darksynth", re.I)


class Playlist:
    """Hands out OSTs without repeating until it has gone through them all."""

    def __init__(self):
        self.left: list[str] = []

    def next(self) -> str:
        if not self.left:
            self.left = random.sample(OSTS, len(OSTS))
        return self.left.pop()


# The loopback recording runs in its own little Python process: `soundcard` can corrupt the heap on some Pythons
# (3.12 from the Microsoft Store does it within seconds), and a crash over there must never take her down with it.
# It prints one "rms low" line per block of what your speakers play.
_EAR = r"""
import sys, warnings
if sys.prefix == sys.base_prefix:  # run.bat's Python: her extra packages live in .deps (a venv has its own)
    sys.path[:0] = [sys.argv[1] + '/.deps']
import numpy as np
warnings.filterwarnings('ignore')
win = np.hanning(1024)

def out(x):
    spec = np.abs(np.fft.rfft(x * win))
    print('%.6f %.5f' % (float(np.sqrt(np.mean(x ** 2))), float(spec[1:8].sum())), flush=True)

try:  # PyAudioWPatch: WASAPI loopback that holds up on every Python
    import pyaudiowpatch as pa
except ImportError:
    pa = None
if pa is not None:
    p = pa.PyAudio()
    lb = p.get_default_wasapi_loopback()
    ch = lb['maxInputChannels']
    st = p.open(format=pa.paFloat32, channels=ch, rate=int(lb['defaultSampleRate']), input=True,
                input_device_index=lb['index'], frames_per_buffer=1024)
    while True:
        out(np.frombuffer(st.read(1024, exception_on_overflow=False), dtype=np.float32).reshape(-1, ch).mean(axis=1))
import soundcard as sc
spk = sc.default_speaker()
mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
with mic.recorder(samplerate=44100, channels=1, blocksize=1024) as rec:
    while True:
        out(rec.record(numframes=1024)[:, 0])
"""


class BeatEar(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.pulse = 0.0  # 0..1, 1 right on a beat
        self.level = 0.0  # smoothed loudness
        self.playing = False
        self.beats: list[float] = []  # recent beat times
        self.stopped = False
        self.ok = False
        self._loud_since = None
        self._quiet_since = time.monotonic()

    @property
    def rhythmic(self) -> bool:
        """A steady beat (music), not one-off bangs from a game or a video."""
        now = time.monotonic()
        recent = [b for b in self.beats if now - b < 4.0]
        if len(recent) < 6:
            return False
        gaps = np.diff(recent)
        return float(np.std(gaps)) < 0.5 * float(np.mean(gaps))

    def _blocks(self):
        """(rms, low) per block from the helper process; restarts it if it dies (crash, device change)."""
        import subprocess
        import sys

        from ..config import ROOT
        from ..portable import spawn

        if getattr(sys, "frozen", False):  # the exe can't run a script: listen in here instead
            yield from self._blocks_here()
            return
        py = sys.executable.replace("pythonw.exe", "python.exe")
        fails = 0
        while not self.stopped and fails < 5:
            proc = spawn([py, "-c", _EAR, str(ROOT)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            got = False
            for line in proc.stdout:
                if self.stopped:
                    break
                try:
                    rms, low = map(float, line.split())
                except ValueError:
                    continue
                got = True
                yield rms, low
            proc.kill()
            fails = 0 if got else fails + 1
            if not self.stopped:
                print("[capri] beat ear restarting")
                time.sleep(3)
        if fails >= 5:
            print("[capri] beat ear unavailable (couldn't listen to the speakers)")

    def _blocks_here(self):
        win = np.hanning(1024)
        try:  # PyAudioWPatch first: soundcard can corrupt the heap, and in here that would take her down too
            import pyaudiowpatch as pa

            p = pa.PyAudio()
            lb = p.get_default_wasapi_loopback()
            ch = lb["maxInputChannels"]
            st = p.open(format=pa.paFloat32, channels=ch, rate=int(lb["defaultSampleRate"]), input=True,
                        input_device_index=lb["index"], frames_per_buffer=1024)
            while not self.stopped:
                x = np.frombuffer(st.read(1024, exception_on_overflow=False), dtype=np.float32).reshape(-1, ch).mean(1)
                yield float(np.sqrt(np.mean(x ** 2))), float(np.abs(np.fft.rfft(x * win))[1:8].sum())
            return
        except ImportError:
            pass
        import soundcard as sc

        warnings.filterwarnings("ignore", message="data discontinuity")
        spk = sc.default_speaker()
        mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
        with mic.recorder(samplerate=44100, channels=1, blocksize=1024) as rec:
            while not self.stopped:
                x = rec.record(numframes=1024)[:, 0]
                spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
                yield float(np.sqrt(np.mean(x ** 2))), float(spec[1:8].sum())

    def run(self):
        avg = 1e-4
        last_beat = 0.0
        self.ok = True
        for rms, low in self._blocks():  # low: ~40-300 Hz, kicks and bass
            now = time.monotonic()
            self.level = self.level * 0.9 + rms * 0.1
            avg = avg * 0.96 + low * 0.04
            if low > avg * 1.6 and low > 0.6 and now - last_beat > 0.22:
                self.pulse, last_beat = 1.0, now
                self.beats = [b for b in self.beats if now - b < 4.0] + [now]
            else:
                self.pulse *= 0.86
            if rms > 0.01:
                self._loud_since = self._loud_since or now
                self._quiet_since = None
            else:
                self._quiet_since = self._quiet_since or now
                if now - self._quiet_since > 1.5:
                    self._loud_since = None
            self.playing = bool(self._loud_since and now - self._loud_since > 2.0)

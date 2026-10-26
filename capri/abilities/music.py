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

    def run(self):
        try:
            import soundcard as sc

            warnings.filterwarnings("ignore", message="data discontinuity")
            spk = sc.default_speaker()
            mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
        except Exception as e:
            print(f"[capri] beat ear unavailable: {e}")
            return
        sr, block = 44100, 1024
        avg = 1e-4
        last_beat = 0.0
        self.ok = True
        while not self.stopped:
            try:
                with mic.recorder(samplerate=sr, channels=1, blocksize=block) as rec:
                    while not self.stopped:
                        x = rec.record(numframes=block)[:, 0]
                        now = time.monotonic()
                        rms = float(np.sqrt(np.mean(x ** 2)))
                        self.level = self.level * 0.9 + rms * 0.1
                        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
                        low = float(spec[1:8].sum())  # ~40-300 Hz: kicks and bass
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
            except Exception as e:  # device switched / unplugged: wait and reopen
                print(f"[capri] beat ear restarting: {e}")
                time.sleep(3)

"""Night Drive: Capri's setup music, an original synthwave loop written from scratch in code (no samples, nothing
borrowed). A minor, 100 BPM, Am - F - C - G. Intro (pads, arp, bass), then the full band with drums and lead, and the
end flows back into the start so it loops clean.

    python tools/installer/make_music.py out.wav
"""
import sys

import numpy as np
from scipy.signal import butter, lfilter

SR = 44100
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(2077)


def hz(note: int) -> float:  # MIDI note -> frequency
    return 440.0 * 2 ** ((note - 69) / 12)


def lp(x, cutoff, order=2):
    b, a = butter(order, min(cutoff, SR / 2 - 100) / (SR / 2), "low")
    return lfilter(b, a, x)


def hp(x, cutoff, order=2):
    b, a = butter(order, cutoff / (SR / 2), "high")
    return lfilter(b, a, x)


def saw(f, t, detune=(0.0,)):
    return sum(2 * ((t * f * (1 + d)) % 1.0) - 1 for d in detune) / len(detune)


def square(f, t, width=0.5):
    return np.where((t * f) % 1.0 < width, 1.0, -1.0)


def env(n, a=0.005, d=0.1, s=0.6, r=0.1, length=None):
    """ADSR over n samples (length = how long the note is held)."""
    length = length if length is not None else n
    t = np.arange(n) / SR
    held = length / SR
    e = np.where(t < a, t / max(a, 1e-4), np.where(t < a + d, 1 - (1 - s) * (t - a) / d, s))
    rel = np.clip(1 - (t - held) / r, 0, 1)
    return e * np.where(t > held, rel, 1.0)


def place(track, start_s, sound, gain=1.0):
    i = int(start_s * SR)
    j = min(len(track), i + len(sound))
    if j > i:
        track[i:j] += gain * sound[: j - i]


# A minor: Am, F, C, G (two bars each), as MIDI notes
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
ROOTS = [45, 41, 48, 43]
SECTION = 8 * BAR  # one pass of the progression
LENGTH = 4 * SECTION  # intro, full, full + lead, breakdown
N = int(LENGTH * SR)
T = np.arange(N) / SR


def pads():
    out = np.zeros(N)
    for s in range(4):
        for c, chord in enumerate(CHORDS):
            start = s * SECTION + c * 2 * BAR
            n = int(2 * BAR * SR + 0.6 * SR)
            t = np.arange(n) / SR
            tone = sum(saw(hz(note), t, (-0.004, 0.0, 0.005)) for note in chord) / 3
            place(out, start, tone * env(n, a=0.4, d=0.5, s=0.8, r=0.6, length=int(2 * BAR * SR)), 0.22)
    sweep = 900 + 1700 * (0.5 + 0.5 * np.sin(2 * np.pi * T / SECTION))  # the filter breathes once per pass
    return lp(out, 2600) * 0.6 + lp(out, 900) * 0.4 * (sweep / 2600)


def bass():
    out = np.zeros(N)
    for s in range(4):
        for c, root in enumerate(ROOTS):
            for k in range(16):  # eighth notes, octave jumps on the off-beats
                start = s * SECTION + c * 2 * BAR + k * BEAT / 2
                note = root + (12 if k % 4 == 3 else 0)
                n = int(BEAT / 2 * SR)
                t = np.arange(n) / SR
                place(out, start, saw(hz(note), t, (0.0, 0.003)) * env(n, a=0.003, d=0.12, s=0.5, r=0.03,
                                                                         length=int(n * 0.85)), 0.5)
    return lp(out, 700)


def arp():
    out = np.zeros(N)
    pattern = [0, 1, 2, 1, 2, 0, 1, 2]
    for s in range(4):
        for c, chord in enumerate(CHORDS):
            for k in range(32):  # sixteenths
                start = s * SECTION + c * 2 * BAR + k * BEAT / 4
                note = chord[pattern[k % 8]] + 12 + (12 if k % 16 >= 12 else 0)
                n = int(BEAT / 4 * SR)
                t = np.arange(n) / SR
                place(out, start, square(hz(note), t, 0.3) * env(n, a=0.002, d=0.08, s=0.2, r=0.02), 0.13)
    out = lp(out, 3500)
    delayed = np.zeros(N)
    d = int(BEAT * 0.75 * SR)  # dotted-eighth echo
    delayed[d:] = out[:-d] * 0.45
    delayed[2 * d:] += out[: -2 * d] * 0.2
    return out + delayed


def lead():
    """The melody (written for this track): half the time sits on the chord, then it lifts."""
    out = np.zeros(N)
    melody = [  # (beat within the 8-bar pass, MIDI note, beats held)
        (0, 76, 1.5), (1.5, 74, 0.5), (2, 72, 1), (3, 74, 1), (4, 76, 2), (6, 79, 2),
        (8, 77, 1.5), (9.5, 76, 0.5), (10, 74, 1), (11, 72, 1), (12, 72, 3), (15, 74, 1),
        (16, 76, 1), (17, 79, 1), (18, 84, 2), (20, 83, 1), (21, 79, 1), (22, 76, 2),
        (24, 74, 1.5), (25.5, 76, 0.5), (26, 79, 1), (27, 74, 1), (28, 71, 3), (31, 69, 1)]
    for s in (2,):  # the third pass carries the lead
        for beat, note, held in melody:
            n = int((held * BEAT + 0.3) * SR)
            t = np.arange(n) / SR
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
            tone = saw(hz(note) * vib, t, (-0.003, 0.003))
            place(out, s * SECTION + beat * BEAT, tone * env(n, a=0.02, d=0.2, s=0.7, r=0.25,
                                                             length=int(held * BEAT * SR)), 0.16)
    out = lp(out, 3000)
    d = int(BEAT * 0.75 * SR)
    echo = np.zeros(N)
    echo[d:] = out[:-d] * 0.35
    return out + echo


def drums():
    out = np.zeros(N)
    kick_n = int(0.35 * SR)
    t = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (45 * t + 90 * (1 - np.exp(-t * 35)) / 35)) * np.exp(-t * 9)
    snare_n = int(0.6 * SR)
    t = np.arange(snare_n) / SR
    noise = rng.standard_normal(snare_n)
    snare = (hp(noise, 1200) * np.exp(-t * 7) * 0.6 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 20) * 0.5)
    snare[int(0.32 * SR):] *= np.linspace(1, 0, snare_n - int(0.32 * SR)) ** 4  # 80s gated tail
    hat_n = int(0.06 * SR)
    t = np.arange(hat_n) / SR
    hat = hp(rng.standard_normal(hat_n), 7000) * np.exp(-t * 60)
    for s in (1, 2):  # drums in the middle two passes
        for b in range(32):
            beat0 = s * SECTION + b * BEAT
            place(out, beat0, kick, 0.9)
            if b % 2 == 1:
                place(out, beat0, snare, 0.55)
            place(out, beat0 + BEAT / 2, hat, 0.18)
            place(out, beat0, hat, 0.1)
    for b in range(28, 32):  # the drums come back in at the end of the intro: a little lift
        place(out, b * BEAT, kick, 0.5 * (b - 27) / 4)
    return out


def main(path: str):
    mix = pads() + bass() * 0.9 + arp() + lead() + drums()
    pump = 1 - 0.35 * np.exp(-((T % BEAT) / 0.12))  # the synths duck on every beat (sidechain feel)
    mix = mix * np.where(T < SECTION, 1.0, pump) + 0 * T
    # tape-ish warmth: a little saturation and a gentle high cut, then stereo from a short Haas delay on the pads
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix = lp(mix, 12000, 1)
    xfade = int(1.5 * SR)  # the end blends into the start so the loop has no seam
    mix[:xfade] = mix[:xfade] * np.linspace(0, 1, xfade) + mix[-xfade:] * np.linspace(1, 0, xfade)
    mix = mix[:-xfade]
    left = mix
    right = np.concatenate([np.zeros(int(0.012 * SR)), mix[: -int(0.012 * SR)]]) * 0.5 + mix * 0.5
    stereo = np.stack([left, right], axis=1)
    stereo = stereo / np.max(np.abs(stereo)) * 0.85
    import wave

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype(np.int16).tobytes())
    print(f"wrote {path} ({len(mix) / SR:.0f} s)")


if __name__ == "__main__":
    main(sys.argv[1])

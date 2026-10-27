"""Turn any Capri clip into voices/capri/ref.wav + ref.txt.

    make_voice.bat "C:\\path\\to\\capri_scene.mp4"             (finds the best 5-10 s line by itself)
    make_voice.bat "C:\\path\\to\\capri_scene.mp4" 83.5 91.2   (or give start/end seconds)

It cuts the audio, transcribes it with ERU's local Whisper, and keeps the clearest stretch of speech.
For scenes with music under her, clean the clip first with UVR5 (vocals only), then run this on the result."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.append(os.path.join(os.path.dirname(HERE), ".deps"))  # imageio-ffmpeg lives there

from capri import config, eru_bridge  # noqa: E402
from capri.abilities.clipper import find_ffmpeg  # noqa: E402

OUT = os.path.join(HERE, "capri")


def cut(ffmpeg: str, src: str, dst: str, start: float | None = None, end: float | None = None) -> None:
    cmd = [ffmpeg, "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", src]
    if end is not None:
        cmd += ["-t", f"{end - (start or 0):.2f}"]
    # mono 24 kHz, light high-pass and loudness normalise; trims nothing else
    cmd += ["-vn", "-ac", "1", "-ar", "24000", "-af", "highpass=f=70,loudnorm=I=-18:TP=-2", dst]
    subprocess.run(cmd, check=True)


def best_window(segs, lo: float = 5.0, hi: float = 10.0):
    """Join consecutive Whisper segments into a 5-10 s stretch with the most confident, speech-only audio."""
    best, best_score = None, -1e9
    for i in range(len(segs)):
        text, start, end, score = [], segs[i].start, segs[i].end, 0.0
        for j in range(i, len(segs)):
            s = segs[j]
            if s.end - start > hi:
                break
            if j > i and s.start - segs[j - 1].end > 0.8:  # a long pause = probably another speaker or a cut
                break
            text.append(s.text.strip())
            end = s.end
            score += s.avg_logprob - 2 * s.no_speech_prob
            dur = end - start
            if dur >= lo:
                avg = score / (j - i + 1)
                if avg > best_score:
                    best, best_score = (max(0.0, start - 0.15), end + 0.25, " ".join(text)), avg
    return best


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    start = float(sys.argv[2]) if len(sys.argv) > 3 else None
    end = float(sys.argv[3]) if len(sys.argv) > 3 else None
    cfg = config.load()
    ffmpeg = find_ffmpeg(cfg)
    from faster_whisper import WhisperModel

    model = WhisperModel(eru_bridge.whisper_model_dir(cfg) or "small", device="cuda", compute_type="int8_float16")
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        full = os.path.join(tmp, "full.wav")
        cut(ffmpeg, src, full, start, end)
        segs, _ = model.transcribe(full, language="en", vad_filter=True, beam_size=5, word_timestamps=False)
        segs = list(segs)
        if not segs:
            sys.exit("No speech found in that clip.")
        if start is not None:
            a, b, text = 0.0, end - start, " ".join(s.text.strip() for s in segs)
        else:
            pick = best_window(segs)
            if not pick:
                sys.exit("Couldn't find a clean 5-10 s stretch of talking. Try a calmer scene or pass start/end seconds.")
            a, b, text = pick
        cut(ffmpeg, full, os.path.join(OUT, "ref.wav"), a, b)
    with open(os.path.join(OUT, "ref.txt"), "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    print(f"Saved voices\\capri\\ref.wav ({b - a:.1f} s) and ref.txt:\n  {text.strip()}")
    print("Listen to ref.wav: it must be only Capri. Fix ref.txt if a word is wrong, then set tts: backend: qwen3.")


if __name__ == "__main__":
    main()

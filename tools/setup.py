"""Second half of setup.bat: writes config.yaml, downloads her brain (Mistral-Nemo GGUF) and ears (faster-whisper),
and checks that the GPU libraries load. Safe to run again: finished downloads are skipped, cut-off ones resume."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capri import config  # noqa: E402


def download(url: str, dest: Path) -> None:
    """Resumable download with a progress line."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "capri-setup", **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req) as r:
        total = have + int(r.headers.get("Content-Length", 0))
        mode = "ab" if have and r.status == 206 else "wb"
        done = have if mode == "ab" else 0
        t0, last = time.time(), 0.0
        with open(part, mode) as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if time.time() - last > 0.5:
                    last = time.time()
                    rate = (done - have) / max(1e-3, last - t0) / 1e6
                    print(f"\r  {done / 1e9:5.2f} / {total / 1e9:.2f} GB  {rate:5.1f} MB/s ", end="", flush=True)
    print()
    part.replace(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", help="use a Mistral-Nemo (or any chat) GGUF you already have instead of downloading")
    args = ap.parse_args()

    cfg_file = ROOT / "config.yaml"
    if not cfg_file.exists():
        shutil.copy(ROOT / "config.example.yaml", cfg_file)
        print("Made config.yaml (edit user_name in it so she knows what to call you).")
    if args.model_path:
        text = cfg_file.read_text(encoding="utf-8")
        line = f"  model_path: '{Path(args.model_path).resolve()}'"
        import re

        text = re.sub(r"^  model_path:.*$", line.replace("\\", "\\\\"), text, count=1, flags=re.M)
        cfg_file.write_text(text, encoding="utf-8")
    cfg = config.load()

    brain = config.model_path(cfg)
    if brain.exists():
        print(f"Brain: {brain} (already there)")
    else:
        print(f"Downloading her brain ({config.MODEL_FILE}, 6.7 GB) ...")
        download(f"https://huggingface.co/{config.MODEL_REPO}/resolve/main/{config.MODEL_FILE}", brain)

    print(f"Ears: faster-whisper {cfg['stt']['model']} ...")
    from huggingface_hub import snapshot_download

    snapshot_download(f"Systran/faster-whisper-{cfg['stt']['model']}", cache_dir=str(config.MODELS / "whisper"))

    print("Checking the GPU libraries ...")
    from capri.cuda import add_dlls

    add_dlls()
    try:
        import ctranslate2

        n = ctranslate2.get_cuda_device_count()
        print(f"  faster-whisper sees {n} CUDA GPU(s)" + ("" if n else ": she'll hear you on the CPU (slower)"))
    except Exception as e:
        print(f"  faster-whisper check failed: {e}")
    try:
        import llama_cpp

        ok = llama_cpp.llama_supports_gpu_offload()
        print("  llama.cpp: GPU ready" if ok else "  llama.cpp: no GPU offload, she'll think on the CPU (slow)")
    except Exception as e:
        print(f"  llama.cpp check failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

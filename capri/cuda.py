"""Make the CUDA DLLs that pip installed (nvidia-cublas-cu12, nvidia-cudnn-cu12, nvidia-cuda-runtime-cu12) findable
for llama.cpp and faster-whisper, so nobody has to install the CUDA toolkit by hand."""
from __future__ import annotations

import os
import site
import sys

_done = False


def add_dlls() -> None:
    global _done
    if _done or os.name != "nt":
        return
    _done = True
    roots = site.getsitepackages() + [site.getusersitepackages()] + [p for p in sys.path if p.endswith("site-packages")]
    for sp in dict.fromkeys(roots):
        nv = os.path.join(sp, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            for sub in ("bin", "lib"):
                d = os.path.join(nv, pkg, sub)
                if os.path.isdir(d):
                    os.add_dll_directory(d)
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

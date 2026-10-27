"""The portable dev build: what it can download, where things go, and finding them again.

Folder layout next to Capri.exe:
    models\\llm\\      brains (.gguf). Drop your own GGUF in here and it shows up in her Brain menu.
    models\\whisper\\  ears (whisper.cpp ggml-*.bin)
    engines\\llama\\   llama.cpp's llama-server (runs any GGUF, new architectures included)
    engines\\whisper\\ whisper.cpp's whisper-server (on the CPU, so the GPU stays free for her brain)
    data\\            her settings and memory (starts empty)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT

MODELS = ROOT / "models"
LLM_DIR = MODELS / "llm"
WHISPER_DIR = MODELS / "whisper"
ENGINES = ROOT / "engines"

LLAMA_TAG = "b11932"  # pinned so every dev runs the same engine
_LLAMA = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/"
_WHISPER = "https://github.com/ggml-org/whisper.cpp/releases/download/b5454/"
_HF = "https://huggingface.co/"


@dataclass
class Item:
    key: str
    label: str
    note: str
    files: list[tuple[str, str, int]]  # (url, path under ROOT, bytes)
    unzip: bool = False

    @property
    def size(self) -> int:
        return sum(f[2] for f in self.files)

    def installed(self) -> bool:
        if self.unzip:
            return (ROOT / self.files[0][1]).parent.joinpath(".done-" + self.key).exists()
        return all((ROOT / p).exists() and (ROOT / p).stat().st_size == n for _, p, n in self.files)


BRAINS = [
    Item("nemo", "Mistral-Nemo 12B", "the smartest one; best for talking one-on-one (needs ~8 GB VRAM)",
         [(_HF + "bartowski/Mistral-Nemo-Instruct-2407-GGUF/resolve/main/Mistral-Nemo-Instruct-2407-IQ4_XS.gguf",
           "models/llm/Mistral-Nemo-Instruct-2407-IQ4_XS.gguf", 6742713472)]),
    Item("conv7b", "Conversational 7B", "fast and chatty; what she uses on streams (~5 GB VRAM)",
         [(_HF + "xiaoheiqaq/conversational-7b-v0.4-Q4_K_M-GGUF/resolve/main/conversational-7b-v0.4-q4_k_m.gguf",
           "models/llm/conversational-7b-v0.4-q4_k_m.gguf", 4372815648)]),
    Item("capriai2", "CapriAI2 (Qwen3.5 4B)", "trained to be Capri; small and new (~4 GB VRAM)",
         [(_HF + "Ghasty3/CapriAI2/resolve/main/Qwen3.5-4B.Q6_K.gguf", "models/llm/CapriAI2-Qwen3.5-4B.Q6_K.gguf",
           3563028064)]),
]
EARS = [
    Item("tiny", "Tiny", "fastest, makes the most mistakes",
         [(_HF + "ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin", "models/whisper/ggml-tiny.en.bin", 77704715)]),
    Item("base", "Base", "fast, decent",
         [(_HF + "ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin", "models/whisper/ggml-base.en.bin", 147964211)]),
    Item("small", "Small", "the sweet spot (what Capri uses)",
         [(_HF + "ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin", "models/whisper/ggml-small.en.bin", 487614201)]),
    Item("medium", "Medium", "most accurate, slower on the CPU",
         [(_HF + "ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin", "models/whisper/ggml-medium.en.bin",
           1533774781)]),
]
ENGINE_GPU = [
    Item("vulkan", "Vulkan", "any GPU (NVIDIA, AMD, Intel); small download",
         [(_LLAMA + f"llama-{LLAMA_TAG}-bin-win-vulkan-x64.zip", "engines/llama/llama-vulkan.zip", 37180481)], True),
    Item("cuda", "CUDA", "NVIDIA only; a bit faster, big download",
         [(_LLAMA + f"llama-{LLAMA_TAG}-bin-win-cuda-12.4-x64.zip", "engines/llama/llama-cuda.zip", 279443090),
          (_LLAMA + "cudart-llama-bin-win-cuda-12.4-x64.zip", "engines/llama/cudart.zip", 391443627)], True),
]
ENGINE_EARS = Item("whisper", "whisper.cpp", "her ears, on the CPU",
                   [(_WHISPER + "whisper-blas-bin-x64.zip", "engines/whisper/whisper.zip", 21715607)], True)


def has_nvidia() -> bool:
    return shutil.which("nvidia-smi") is not None or Path(r"C:\Windows\System32\nvidia-smi.exe").exists()


def finish(item: Item) -> None:
    """After an engine's zips are downloaded: unpack them flat into the engine folder, drop the zips."""
    if not item.unzip:
        return
    folder = (ROOT / item.files[0][1]).parent
    for _, p, _ in item.files:
        z = ROOT / p
        with zipfile.ZipFile(z) as zf:
            for m in zf.infolist():
                if m.is_dir():
                    continue
                target = folder / Path(m.filename).name  # flat: the exes and their DLLs side by side
                with zf.open(m) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        z.unlink()
    for other in ENGINE_GPU:  # one llama engine at a time
        if other is not item:
            folder.joinpath(".done-" + other.key).unlink(missing_ok=True)
    folder.joinpath(".done-" + item.key).write_text("ok")


def find_exe(name: str) -> Path | None:
    for p in ENGINES.rglob(name):
        return p
    return None


def brains() -> list[Path]:
    """Every .gguf in models\\llm (the catalog's and any a dev dropped in), minus vision add-on files."""
    if not LLM_DIR.exists():
        return []
    return sorted(p for p in LLM_DIR.rglob("*.gguf") if "mmproj" not in p.name.lower())


def ears_models() -> list[Path]:
    return sorted(WHISPER_DIR.glob("ggml-*.bin")) if WHISPER_DIR.exists() else []


def needs_setup() -> bool:
    return not brains() or find_exe("llama-server.exe") is None


def no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


_job = None


def tie_to_me(proc) -> None:
    """Put a helper process (llama-server, whisper-server) in a Windows job that dies with Capri, so a crash or a
    killed Capri never leaves them running in the background."""
    global _job
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.windll.kernel32
    if _job is None:
        class Limits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

        class Extended(ctypes.Structure):
            _fields_ = [("Basic", Limits), ("Io", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32.CreateJobObjectW.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        info = Extended()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info))
        _job = job
    k32.AssignProcessToJobObject(wintypes.HANDLE(_job), wintypes.HANDLE(int(proc._handle)))

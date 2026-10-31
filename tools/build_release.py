"""Builds Capri-Setup.exe: Capri.exe (PyInstaller, from this repo's .venv), her cloned voice model and the release
config, packed into one installer. Never copies data\\ (memory, settings, chat logs) or your config.yaml.

    .venv\\Scripts\\python.exe tools\\build_release.py [out dir]      (default: build\\release in this folder)

Needs Inno Setup 6 (https://jrsoftware.org/isinfo.php) and her voice model in models\\voice\\capri-clone.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC / "build" / "release"
PY = sys.executable
WORK = OUT / "work"
VERSION = "0.5.0"


def pyinstaller(*args):
    subprocess.run([PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", str(WORK), "--specpath", str(WORK),
                    *args], check=True, cwd=str(OUT))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    ico = WORK / "capri.ico"
    WORK.mkdir(parents=True, exist_ok=True)
    Image.open(SRC / "assets" / "icons" / "capri.png").save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                                                                          (128, 128), (256, 256)])
    # packages built with delvewheel keep their DLLs in a "<name>.libs" folder next to them, which PyInstaller misses
    # (onnx without onnx.libs: "DLL load failed while importing onnx_cpp2py_export")
    import sysconfig

    site = Path(sysconfig.get_paths()["purelib"])
    libs = [a for d in site.glob("*.libs") if not d.name.startswith("~")
            for a in ("--add-binary", f"{d};{d.name}")]
    # 1) Capri.exe
    pyinstaller("--windowed", "--name", "Capri", "--distpath", str(OUT / "dist"), "--icon", str(ico), *libs,
                "--collect-all", "onnx", "--collect-all", "ml_dtypes",
                "--add-data", f"{SRC / 'assets'};assets", "--add-data", f"{ico};assets/icons",
                "--paths", str(SRC), "--collect-submodules", "capri",
                "--collect-all", "winocr", "--collect-all", "winrt", "--collect-all", "genie_tts",
                "--collect-all", "sherpa_onnx", "--collect-all", "onnxruntime", "--collect-all", "pyaudiowpatch",
                "--collect-all", "pyopenjtalk", "--collect-data", "g2pM", "--collect-data", "pypinyin",
                "--hidden-import", "win32com.client",
                *[a for m in ("torch", "transformers", "llama_cpp", "faster_whisper", "ctranslate2", "TikTokLive",
                              "tkinter", "matplotlib", "pytest", "PyInstaller")
                  for a in ("--exclude-module", m)],
                str(SRC / "capri_dev.py"))
    app = OUT / "dist" / "Capri"
    if (OUT / "dist" / "capri_dev").exists():
        (OUT / "dist" / "capri_dev").rename(app)
    shutil.copy2(SRC / "portable" / "config.yaml", app / "config.yaml")
    shutil.copy2(SRC / "portable" / "README.txt", app / "README.txt")
    clone = SRC / "models" / "voice" / "capri-clone"
    shutil.copytree(clone, app / "models" / "voice" / "capri-clone", dirs_exist_ok=True)  # her voice ships with her
    for d in ("models/llm", "models/whisper", "engines"):
        (app / d).mkdir(parents=True, exist_ok=True)
    # 2) the setup wizard (Inno Setup): components + downloads generated from capri/portable.py's lists
    media = SRC / "tools" / "installer" / "media"
    shutil.copy2(ico, media / "capri.ico")
    sys.path.insert(0, str(SRC / "tools" / "installer"))
    import wizard_gen

    wizard_gen.main()
    iscc = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
    subprocess.run([str(iscc), f"/DAppDir={app}", f"/DVersion={VERSION}", f"/DMedia={media}", f"/DOut={OUT}",
                    str(SRC / "tools" / "installer" / "capri.iss")], check=True)
    size = (OUT / "Capri-Setup.exe").stat().st_size
    print(f"\nDone: {OUT / 'Capri-Setup.exe'}  ({size / 2 ** 20:.0f} MB)")


if __name__ == "__main__":
    main()

"""Build the native Windows x64 portable bundle and optional installer."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "build" / "release"
OUTPUT = ROOT / "dist" / "release"
BUNDLE = WORK / "dist" / "Capri"


def version() -> str:
    tree = ast.parse((ROOT / "capri" / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and all(p.isdigit() for p in value.split(".")) and len(value.split(".")) == 3:
                return value
    raise ValueError("Expected a numeric MAJOR.MINOR.PATCH in capri/__init__.py")


def run(args: list[str], **kwargs) -> None:
    print("Running:", subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, check=True, cwd=ROOT, **kwargs)


def smoke(bundle: Path = BUNDLE) -> None:
    exe = bundle / "Capri.exe"
    if not exe.is_file():
        raise FileNotFoundError(exe)
    with tempfile.TemporaryDirectory(prefix="capri-smoke-") as temp:
        home = Path(temp)
        report = home / "report.json"
        env = dict(os.environ, CAPRI_HOME=temp, QT_QPA_PLATFORM="offscreen")
        try:
            run([str(exe), "--smoke-test", str(report)], env=env, timeout=90)
        finally:
            if report.exists():
                WORK.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report, WORK / "smoke-windows.json")
                print(report.read_text(encoding="utf-8"), flush=True)
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result.get("ok") or result.get("version") != version() or result.get("edition") != "dev" or not result.get("frozen"):
            raise RuntimeError("Frozen smoke report did not confirm the expected release configuration")
        if not (home / "config.yaml").is_file():
            raise RuntimeError("Frozen first start did not create config.yaml")
        WORK.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report, WORK / "smoke-windows.json")


def find_iscc(override: str | None) -> str:
    candidates = [override, shutil.which("ISCC.exe")]
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(var):
            candidates.append(str(Path(os.environ[var]) / "Inno Setup 6" / "ISCC.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Install Inno Setup 6 or pass --iscc PATH_TO_ISCC.exe")


def copy_notices(bundle: Path) -> None:
    """Keep the license and metadata notices distributed with installed wheels."""
    destination = bundle / "THIRD-PARTY"
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        for relative in distribution.files or ():
            parts = relative.parts
            if not parts or not parts[0].endswith(".dist-info"):
                continue
            if relative.name != "METADATA" and not any(
                "license" in part.lower() or "copying" in part.lower() or "notice" in part.lower()
                for part in parts[1:]
            ):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                target = destination / name / Path(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def build(installer: bool, iscc: str | None) -> None:
    from PIL import Image

    app_version = version()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    icon = WORK / "capri.ico"
    with Image.open(ROOT / "assets" / "icons" / "capri.png") as image:
        image.save(icon, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
               "--name", "Capri", "--noupx", "--icon", str(icon),
               "--distpath", str(WORK / "dist"), "--workpath", str(WORK / "pyinstaller"),
               "--specpath", str(WORK), "--paths", str(ROOT),
               "--add-data", f"{ROOT / 'assets'}:assets",
               "--add-data", f"{ROOT / 'portable' / 'config.yaml'}:portable"]
    for module in ("sounddevice", "soundfile", "pyaudiowpatch", "winocr"):
        command += ["--collect-all", module]
    for module in ("win32api", "win32con", "win32gui"):
        command += ["--hidden-import", module]
    command.append(str(ROOT / "capri_dev.py"))
    # PyInstaller resolves native DLLs through PATH. Desktop tools can add their
    # own incompatible ICU/Qt DLLs there; use only this Python and Windows.
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    build_env = dict(os.environ, PATH=os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows,
    ))))
    run(command, env=build_env)
    shutil.copy2(icon, BUNDLE / "capri.ico")
    shutil.copy2(ROOT / "LICENSE", BUNDLE / "LICENSE.txt")
    shutil.copy2(ROOT / "portable" / "README.txt", BUNDLE / "README.txt")
    copy_notices(BUNDLE)
    shutil.copytree(Path(__file__).with_name("licenses"), BUNDLE / "licenses", dirs_exist_ok=True)
    shutil.copy2(Path(__file__).with_name("THIRD-PARTY.txt"), BUNDLE / "THIRD-PARTY.txt")
    smoke()
    archive = OUTPUT / "Capri-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(BUNDLE.rglob("*")):
            if path.is_file():
                z.write(path, Path("Capri") / path.relative_to(BUNDLE))
    artifacts = [archive]
    if installer:
        run([find_iscc(iscc), f"/DAppVersion={app_version}", f"/DBundleDir={BUNDLE}",
             f"/DOutputDir={OUTPUT}", f"/DRepoDir={ROOT}", str(Path(__file__).with_name("capri.iss"))])
        artifacts.append(OUTPUT / "Capri-Setup.exe")
    checksums = []
    for path in artifacts:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        checksums.append(f"{digest.hexdigest()}  {path.name}\n")
    (OUTPUT / "SHA256SUMS").write_text("".join(checksums), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["windows"], default="windows")
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--iscc")
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64") or sys.maxsize <= 2**32:
        parser.error("Windows packaging requires native Windows x64 with 64-bit Python")
    if args.smoke_only:
        smoke()
    else:
        build(args.installer, args.iscc)


if __name__ == "__main__":
    main()

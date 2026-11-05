"""Exercise install, reinstall and uninstall in a disposable directory on Windows."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import time
import winreg

from build import OUTPUT, WORK, smoke

KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{9D58FAD0-FA8F-47EC-A526-028E4EA94201}_is1"


def registered() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY):
            return True
    except FileNotFoundError:
        return False


def uninstall(target: Path) -> None:
    if not target.resolve().is_relative_to(WORK.resolve()):
        raise RuntimeError("Refusing to uninstall outside the disposable build directory")
    executable = target / "unins000.exe"
    if executable.exists():
        subprocess.run([str(executable), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        f"/LOG={WORK / 'installer-uninstall.log'}"], check=True, timeout=180)
    for _ in range(100):
        if not registered() and not executable.exists():
            break
        time.sleep(0.1)
    if registered():
        raise RuntimeError("Disposable installer registration was not removed")


def main() -> None:
    # Do not replace a real installation's registration while testing.
    if registered():
        raise RuntimeError("An installed Capri with this AppId already exists; use a clean test machine")
    installer = OUTPUT / "Capri-Setup.exe"
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="installer-", dir=WORK) as temp:
        target = Path(temp) / "Capri"
        options = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", f"/DIR={target}",
                   f"/GROUP=Capri Release Test {Path(temp).name}", "/TASKS="]
        command = [str(installer), *options]
        sentinel = {
            "config.yaml": b"edition: dev\nuser_name: preserved-release-test\n",
            "data/memory.json": b'{"test": "keep memory"}',
            "models/llm/preservation.txt": b"keep downloaded models",
            "engines/preservation.txt": b"keep downloaded engines",
        }
        try:
            subprocess.run(command + [f"/LOG={WORK / 'installer-install.log'}"], check=True, timeout=180)
            smoke(target)
            for name, content in sentinel.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            subprocess.run(command + [f"/LOG={WORK / 'installer-upgrade.log'}"], check=True, timeout=180)
            assert all((target / name).read_bytes() == content for name, content in sentinel.items()), "Reinstall changed user files"
        finally:
            uninstall(target)
        assert not (target / "Capri.exe").exists(), "Uninstall left the application executable"
        assert all((target / name).read_bytes() == content for name, content in sentinel.items()), "Uninstall removed user files"
        result = {"ok": True, "install_smoke": True, "reinstall_preserves_user_files": True,
                  "uninstall_preserves_user_files": True}
        (WORK / "installer-test.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

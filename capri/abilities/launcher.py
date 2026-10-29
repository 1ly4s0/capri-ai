"""Open stuff on the PC: apps, sites, Google / image / YouTube searches."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import sys
import urllib.parse
import webbrowser

# spoken name -> what to launch (URI schemes work through the Windows shell)
APPS = {
    "spotify": "spotify:",
    "discord": "discord:",
    "steam": "steam:",
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "twitch": "https://www.twitch.tv",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "netflix": "https://www.netflix.com",
    "chatgpt": "https://chatgpt.com",
    "browser": "https://www.google.com",
    "brave": "brave.exe",
    "brave browser": "brave.exe",
    "chrome": "chrome",
    "edge": "msedge",
    "firefox": "firefox",
    "opera": "opera",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "cmd": "cmd",
    "terminal": "wt",
    "obs": "obs64",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "minecraft": "minecraft:",
    "epic games": "com.epicgames.launcher:",
}


def _browser(url: str) -> None:
    """Open a URL without blocking her reply (a cold browser start can take a while)."""
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()


def _launch(target: str) -> bool:
    if target.startswith(("http://", "https://")):
        _browser(target)
        return True
    if sys.platform == "win32":
        try:
            os.startfile(target)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    if target.endswith(":"):  # app links like minecraft: / ms-settings:
        from .. import linux

        return linux.open_path(target)
    name = target.removesuffix(".exe")
    exe = next((e for e in (shutil.which(n) for n in (name, LINUX_NAMES.get(name, ""))) if e), None)
    if exe:
        subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    return False


# Windows program names -> what they're called on Linux (first one installed wins)
LINUX_NAMES = {"chrome": "google-chrome-stable", "msedge": "microsoft-edge-stable", "notepad": "kate",
               "calc": "kcalc", "mspaint": "kolourpaint", "explorer": "dolphin", "taskmgr": "plasma-systemmonitor",
               "cmd": "konsole", "wt": "konsole", "obs64": "obs", "brave": "brave"}


def open_thing(name: str, google_fallback: bool = True) -> str:
    """'spotify' -> opens Spotify. Unknown names are tried as a program, then (if allowed) as a web search."""
    key = name.lower().strip(" .!?").removeprefix("the ").removesuffix(" app")
    target = APPS.get(key)
    if target and _launch(target):
        return f"opened {key}"
    if "." in key and " " not in key:  # looks like a domain
        _browser("https://" + key)
        return f"opened {key}"
    if (lnk := find_shortcut(key)) and _launch(str(lnk)):
        return f"opened {lnk.stem}"
    if (app := find_store_app(key)) and _launch("shell:AppsFolder\\" + app[1]):
        return f"opened {app[0]}"
    if _launch(key):
        return f"opened {key}"
    if not google_fallback:
        return f"couldn't find an app called {key}"
    web_search(key)
    return f"couldn't find an app called {key}, googled it instead"


def find_shortcut(name: str):
    """Any installed app by the name you'd say: the best-matching Start Menu or desktop shortcut ('whatsapp' ->
    WhatsApp.lnk, 'valorant' -> VALORANT.lnk, 'premiere' -> Adobe Premiere Pro 2025.lnk). None if nothing fits."""
    if sys.platform != "win32":
        return None
    from pathlib import Path

    want = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    if len(want) < 2:
        return None
    roots = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
             Path.home() / "Desktop", Path.home() / "OneDrive/Desktop", Path(os.environ.get("PUBLIC", "")) / "Desktop"]
    best, score = None, 0.0
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in (".lnk", ".url", ".appref-ms"):
                continue
            label = re.sub(r"[^a-z0-9]+", " ", p.stem.lower()).strip()
            if re.search(r"\b(?:uninstall|readme|help|manual|website|documentation|release notes)\b", label):
                continue
            if label == want:
                s = 3.0
            elif re.search(rf"\b{re.escape(want)}\b", label):
                s = 2.0 - len(label) / 200  # 'discord' in 'discord ptb' beats 'discord bot maker manual'
            elif label.replace(" ", "").startswith(want.replace(" ", "")):
                s = 1.5 - len(label) / 200
            else:
                continue
            if s > score:
                best, score = p, s
    return best


_start_apps: list[tuple[str, str]] | None = None


def find_store_app(name: str) -> tuple[str, str] | None:
    """Microsoft Store apps (WhatsApp, Xbox, Photos...) have no shortcut file: Windows' own Start list has them.
    -> (name, AppID), launched through shell:AppsFolder. The list is read once (about a second)."""
    global _start_apps
    if sys.platform != "win32":
        return None
    if _start_apps is None:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "Get-StartApps | ForEach-Object { $_.Name + \"`t\" + $_.AppID }"],
                                 capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            _start_apps = [tuple(line.split("\t", 1)) for line in out.splitlines() if "\t" in line]
        except Exception as e:
            print(f"[capri] couldn't list Start apps: {e}")
            return None
    want = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    hits = [(n, a) for n, a in _start_apps if re.search(rf"\b{re.escape(want)}\b", re.sub(r"[^a-z0-9]+", " ", n.lower()))
            and not re.search(r"\buninstall\b", n, re.I)]
    return min(hits, key=lambda h: len(h[0])) if hits else None


_yt = None


def warm_youtube() -> None:
    """Open the connection to YouTube ahead of time, so the first "play X" doesn't pay for the handshake."""
    global _yt
    try:
        import requests

        _yt = requests.Session()
        _yt.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en"})
        _yt.get("https://www.youtube.com/results", params={"search_query": "cyberpunk"}, timeout=6, stream=True).close()
    except Exception as e:
        print(f"[capri] youtube warm-up failed: {e}")


def youtube_play(query: str) -> str:
    """Open the top YouTube result for `query` straight away (falls back to the results page). Reads the results
    page as a stream and stops as soon as the first video and its title have arrived."""
    import re

    global _yt
    try:
        import requests

        if _yt is None:  # one kept-alive connection: no new TLS handshake per song
            _yt = requests.Session()
            _yt.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en"})
        found = re.compile(r'"videoRenderer":\{"videoId":"([\w-]{11})".*?"title":\{"runs":\[\{"text":"(.*?)"\}', re.S)
        buf = ""
        with _yt.get("https://www.youtube.com/results", params={"search_query": query}, timeout=6, stream=True) as r:
            raw = b""
            for chunk in r.iter_content(65536):  # raw bytes: no slow charset sniffing
                raw += chunk
                start = raw.find(b'"videoRenderer"')
                if start >= 0 and raw.find(b'"title"', start) >= 0 and found.search(raw[start:].decode("utf-8", "ignore")):
                    break
            buf = raw.decode("utf-8", "ignore")
        m = found.search(buf)
        if m:
            _browser(f"https://www.youtube.com/watch?v={m.group(1)}")
            import json

            try:
                title = json.loads('"' + m.group(2) + '"')  # JSON escapes like &, without mangling accents
            except ValueError:
                title = m.group(2)
            return f"playing {title} on YouTube"
    except Exception as e:
        print(f"[capri] youtube lookup failed: {e}")
    return web_search(query, "youtube")


def web_search(query: str, kind: str = "web") -> str:
    q = urllib.parse.quote_plus(query)
    url = {
        "images": f"https://www.google.com/search?tbm=isch&q={q}",
        "youtube": f"https://www.youtube.com/results?search_query={q}",
        "web": f"https://www.google.com/search?q={q}",
    }[kind]
    _browser(url)
    label = {"images": "pictures of", "youtube": "YouTube for", "web": "Google for"}[kind]
    return f"opened {label} {query}"

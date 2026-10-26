"""Open stuff on the PC: apps, sites, Google / image / YouTube searches."""
from __future__ import annotations

import os
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
    exe = shutil.which(target)
    if exe:
        subprocess.Popen([exe])
        return True
    return False


def open_thing(name: str, google_fallback: bool = True) -> str:
    """'spotify' -> opens Spotify. Unknown names are tried as a program, then (if allowed) as a web search."""
    key = name.lower().strip(" .!?").removeprefix("the ").removesuffix(" app")
    target = APPS.get(key)
    if target and _launch(target):
        return f"opened {key}"
    if "." in key and " " not in key:  # looks like a domain
        _browser("https://" + key)
        return f"opened {key}"
    if _launch(key):
        return f"opened {key}"
    if not google_fallback:
        return f"couldn't find an app called {key}"
    web_search(key)
    return f"couldn't find an app called {key}, googled it instead"


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

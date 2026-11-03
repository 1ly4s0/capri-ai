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
    "epic": "com.epicgames.launcher:",
    # the same apps said in her other languages
    "стим": "steam:", "дискорд": "discord:", "спотифай": "spotify:", "ютуб": "https://www.youtube.com",
    "калькулятор": "calc", "блокнот": "notepad", "браузер": "https://www.google.com", "проводник": "explorer",
    "calculadora": "calc", "calculatrice": "calc", "rechner": "calc", "taschenrechner": "calc", "calcolatrice": "calc",
    "kalkulator": "calc", "navegador": "https://www.google.com", "navigateur": "https://www.google.com",
    "configuración": "ms-settings:", "einstellungen": "ms-settings:", "paramètres": "ms-settings:",
    "impostazioni": "ms-settings:", "ustawienia": "ms-settings:", "настройки": "ms-settings:",
    "bloc de notas": "notepad", "bloc-notes": "notepad", "editor": "notepad", "explorador": "explorer",
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
    if target.endswith(":") or re.match(r"^[a-z][\w.+-]*://", target):  # app links: minecraft: / steam://rungameid/...
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


# "peak on steam", "fortnite from epic", "minecraft in the launcher": the store/launcher it lives in
_ON_STORE = re.compile(r"^(?P<what>.+?)\s+(?:on|in|from|via|through|with|using|en|sur|auf|in|na|w|в|через)\s+"
                       r"(?:my\s+|the\s+|mi\s+|mon\s+|meinem\s+)?(?P<store>steam|epic(?: games)?(?: launcher)?|"
                       r"battle\.?net|ea(?: app)?|origin|ubisoft(?: connect)?|uplay|gog(?: galaxy)?|xbox(?: app)?|"
                       r"riot(?: client)?)$", re.I)
_SAY_GAME = re.compile(r"^(?:the\s+)?(?:game|app|program)\s+(?:called\s+|named\s+)?|\s+(?:game|app)$", re.I)


def _clean_name(name: str) -> str:
    key = re.sub(r"\s+", " ", name.lower().strip(" .!?,\"'")).removeprefix("the ").removesuffix(" app").strip()
    return _SAY_GAME.sub("", key).strip() or key


def open_thing(name: str, google_fallback: bool = False) -> str:
    """'spotify' -> opens Spotify; 'peak on steam' -> starts PEAK through Steam. Unknown names are tried as a Steam
    game, a shortcut, a Store app and a program. Asked to OPEN something, she never googles it instead (testers got
    a browser search for "open peak on steam"); only a domain opens in the browser."""
    key = _clean_name(name)
    store = ""
    if m := _ON_STORE.match(key):
        key, store = _clean_name(m.group("what")), m.group("store").lower()
    target = APPS.get(key)
    if target and not store and _launch(target):
        return f"opened {key}"
    if "." in key and " " not in key and not store:  # looks like a domain
        _browser("https://" + key)
        return f"opened {key}"
    if store.startswith("steam") or not store:
        game = find_steam_game(key)
        if game and _launch(f"steam://rungameid/{game[0]}"):
            return f"started {game[1]} on Steam"
    if (lnk := find_shortcut(key)) and _launch(str(lnk)):
        return f"opened {lnk.stem}"
    if (app := find_store_app(key)) and _launch("shell:AppsFolder\\" + app[1]):
        return f"opened {app[0]}"
    if store.startswith("steam"):  # not installed: open it in Steam's own store, never a Google search
        if _launch("steam://openurl/https://store.steampowered.com/search/?term=" + urllib.parse.quote(key)):
            return f"couldn't find {key} in their Steam library, opened it in the Steam store"
    if store:
        launcher = {"epic": "epic games", "xbox": "xbox"}.get(store.split()[0], store.split()[0])
        if (lnk := find_shortcut(launcher)) and _launch(str(lnk)):
            return f"couldn't find {key}, opened {lnk.stem} instead"
        if APPS.get(launcher) and _launch(APPS[launcher]):
            return f"couldn't find {key}, opened {launcher} instead"
    if " " not in key and _launch(key):  # a program on PATH ("notepad", "code"); never a whole sentence
        return f"opened {key}"
    if not google_fallback:
        return f"couldn't find an app or game called {key} on this PC"
    web_search(key)
    return f"couldn't find an app called {key}, googled it instead"


def _steam_roots() -> list:
    """Steam's library folders on this PC (the main install plus every extra library drive)."""
    from pathlib import Path

    homes = []
    if sys.platform == "win32":
        try:
            import winreg

            for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        homes.append(Path(winreg.QueryValueEx(k, val)[0]))
                except OSError:
                    pass
        except ImportError:
            pass
        homes += [Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
                  Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Steam"]
    else:
        h = Path.home()
        homes += [h / ".local/share/Steam", h / ".steam/steam", h / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
    libs, seen = [], set()
    for home in homes:
        vdf = home / "steamapps" / "libraryfolders.vdf"
        found = [home]
        try:
            found += [Path(p.replace("\\\\", "\\")) for p in
                      re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
        except OSError:
            pass
        for lib in found:
            key = os.path.normcase(str(lib))
            if key not in seen and (lib / "steamapps").is_dir():
                seen.add(key)
                libs.append(lib)
    return libs


def steam_games() -> list[tuple[str, str]]:
    """Every installed Steam game: (appid, name), from the appmanifest files in each library."""
    out = []
    for lib in _steam_roots():
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            appid = re.search(r'"appid"\s+"(\d+)"', text)
            name = re.search(r'"name"\s+"([^"]+)"', text)
            if appid and name and not re.search(r"\b(?:redistributable|steamworks|proton|runtime)\b", name.group(1), re.I):
                out.append((appid.group(1), name.group(1)))
    return out


def find_steam_game(name: str) -> tuple[str, str] | None:
    """'peak' -> ('3527290', 'PEAK'); 'cs2' / 'counter strike' -> Counter-Strike 2. None when it isn't installed."""
    want = re.sub(r"[^\w]+", " ", name.lower()).strip()
    if len(want) < 2:
        return None
    best, score = None, 0.0
    for appid, title in steam_games():
        label = re.sub(r"[^\w]+", " ", title.lower()).strip()
        initials = "".join(w[0] for w in label.split() if w and not w.isdigit()) + "".join(
            w for w in label.split() if w.isdigit())
        if label == want:
            s = 3.0
        elif want == initials or want.replace(" ", "") == label.replace(" ", ""):
            s = 2.5
        elif re.search(rf"\b{re.escape(want)}\b", label):
            s = 2.0 - len(label) / 200
        elif label.startswith(want):
            s = 1.5 - len(label) / 200
        else:
            continue
        if s > score:
            best, score = (appid, title), s
    return best


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

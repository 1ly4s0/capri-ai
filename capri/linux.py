"""Linux stand-ins for the Windows bits: keys held down, idle time, open windows and their titles, screenshots.

Keys and idle come straight from the kernel (/dev/input/event*), which works on X11 and Wayland alike but needs
the user in the `input` group; without it they fall back to X11. Windows come from X11 (python-xlib). Capri runs
through XWayland on Wayland desktops (capri_dev.py sets QT_QPA_PLATFORM=xcb) because Wayland won't let an app put
its own windows where it wants; there X11 can't see native Wayland windows, so on KDE her eyes go through a KWin
script (capri/kwin/capri-active, installed by ensure_watch) that reports the active window into a config file.
"""
from __future__ import annotations

import glob
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time

WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


# -- keys and idle, from the kernel -------------------------------------------------------------
class _Input:
    """One thread reading every input device we're allowed to open: which keys are down, when anything last moved."""
    EV = struct.Struct("llHHi")  # struct input_event on 64-bit: timeval, type, code, value

    def __init__(self):
        self.down: set[int] = set()
        self.last = time.monotonic()
        self.fds = []
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                self.fds.append(os.open(path, os.O_RDONLY | os.O_NONBLOCK))
            except OSError:
                pass
        if self.fds:
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import select

        size = self.EV.size
        while True:
            try:
                ready, _, _ = select.select(self.fds, [], [], 5)
            except (OSError, ValueError):
                return
            for fd in ready:
                try:
                    data = os.read(fd, size * 64)
                except BlockingIOError:
                    continue
                except OSError:  # unplugged
                    self.fds.remove(fd)
                    continue
                for i in range(0, len(data) - size + 1, size):
                    _, _, typ, code, value = self.EV.unpack_from(data, i)
                    if typ in (1, 2, 3):  # keys / buttons, mouse moves, touchpads
                        self.last = time.monotonic()
                    if typ == 1:
                        if value:
                            self.down.add(code)
                        else:
                            self.down.discard(code)


_input = None


def _kernel() -> _Input | None:
    global _input
    if _input is None:
        _input = _Input()
    return _input if _input.fds else None


def keys_down() -> set[int]:
    """Linux key codes (KEY_* from linux/input-event-codes.h) held right now."""
    k = _kernel()
    if k:
        return set(k.down)
    d = _display()
    if d is None:
        return set()
    try:
        bits = d.query_keymap()  # X11 keycode = kernel code + 8 (only sees keys while an X11 window has focus)
    except Exception:
        return set()
    return {i * 8 + b - 8 for i, byte in enumerate(bits) for b in range(8) if byte >> b & 1 and i * 8 + b >= 8}


def can_hear_keys() -> bool:
    return _kernel() is not None or (_display() is not None and not WAYLAND)


def idle_seconds() -> float:
    k = _kernel()
    if k:
        return time.monotonic() - k.last
    d = _display()
    if d is not None and not WAYLAND:
        try:
            return d.screen().root.screensaver_query_info().idle / 1000.0
        except Exception:
            pass
    return 0.0


# -- windows, from X11 ------------------------------------------------------------------------------
_disp = False


def _display():
    global _disp
    if _disp is False:
        try:
            import Xlib.threaded  # noqa: F401  (her eyes and ledges ask from different threads)
            from Xlib import display

            _disp = display.Display()
        except Exception:
            _disp = None
    return _disp


def _atom(name):
    return _display().intern_atom(name)


def _prop(win, name, kind=None):
    try:
        p = win.get_full_property(_atom(name), kind if kind is not None else 0)
    except Exception:
        return None
    return p.value if p is not None else None


def _title(win) -> str:
    v = _prop(win, "_NET_WM_NAME", _atom("UTF8_STRING"))
    if v is None:
        v = _prop(win, "WM_NAME")
    if isinstance(v, bytes):
        return v.decode("utf-8", "ignore")
    return v or ""


def _states(win) -> set[str]:
    d = _display()
    return {d.get_atom_name(a) for a in (_prop(win, "_NET_WM_STATE") or [])}


def windows() -> list[tuple[int, tuple[int, int, int, int], str, set[str]]]:
    """(id, (left, top, right, bottom) in X11 pixels incl. the title bar, title, states) for every app window
    on the current desktop, top of the stack first."""
    d = _display()
    if d is None:
        return []
    root = d.screen().root
    ids = _prop(root, "_NET_CLIENT_LIST_STACKING") or _prop(root, "_NET_CLIENT_LIST") or []
    cur = (_prop(root, "_NET_CURRENT_DESKTOP") or [0])[0]
    keep = {_atom("_NET_WM_WINDOW_TYPE_NORMAL"), _atom("_NET_WM_WINDOW_TYPE_DIALOG")}
    out = []
    for wid in reversed(list(ids)):
        try:
            w = d.create_resource_object("window", wid)
            types = set(_prop(w, "_NET_WM_WINDOW_TYPE") or [])
            if types and not types & keep:
                continue
            desk = (_prop(w, "_NET_WM_DESKTOP") or [cur])[0]
            if desk not in (cur, 0xFFFFFFFF):
                continue
            states = _states(w)
            if "_NET_WM_STATE_HIDDEN" in states or w.get_attributes().map_state != 2:
                continue
            g = w.get_geometry()
            pos = w.translate_coords(root, 0, 0)
            x, y = -pos.x, -pos.y
            le, ri, to, bo = (_prop(w, "_NET_FRAME_EXTENTS") or [0, 0, 0, 0])[:4]
            out.append((wid, (x - le, y - to, x + g.width + ri, y + g.height + bo), _title(w), states))
        except Exception:
            continue
    return out


def window_box(wid: int):
    """(left, top, right, bottom, states) of one window, or None once it's gone / minimized."""
    for w, box, _, states in windows():
        if w == wid:
            return box, states
    return None


def active_title() -> str:
    w = _watch_data()
    if w and w[0]:
        return w[0]
    d = _display()
    if d is None:
        return ""
    try:
        wid = (_prop(d.screen().root, "_NET_ACTIVE_WINDOW") or [0])[0]
        return _title(d.create_resource_object("window", wid)) if wid else ""
    except Exception:
        return ""


def active_app() -> str:
    """The program behind the active window: KWin's app id on KDE / Wayland, else the X11 window's process name
    (from _NET_WM_PID), else its WM_CLASS. '' if it can't be told."""
    w = _watch_data()
    if w and w[1]:
        return str(w[1]).rsplit(".", 1)[-1]  # "org.kde.dolphin" -> "dolphin", "spotify" stays
    d = _display()
    if d is None:
        return ""
    try:
        wid = (_prop(d.screen().root, "_NET_ACTIVE_WINDOW") or [0])[0]
        if not wid:
            return ""
        win = d.create_resource_object("window", wid)
        pid = (_prop(win, "_NET_WM_PID") or [0])[0]
        if pid:
            try:
                with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                    return f.read().strip()
            except OSError:
                pass
        cls = win.get_wm_class()
        return cls[1] if cls else ""
    except Exception:
        return ""


def active_box():
    w = _watch_data()
    if w and w[2][2] > 0 and w[2][3] > 0:
        x, y, wid, hei = w[2]
        return x, y, x + wid, y + hei
    d = _display()
    if d is None:
        return None
    wid = (_prop(d.screen().root, "_NET_ACTIVE_WINDOW") or [0])[0]
    hit = window_box(wid) if wid else None
    return hit[0] if hit else None


def titles() -> list[str]:
    out = [t for _, _, t, _ in windows() if t]
    w = _watch_data()
    if w and w[0] and w[0] not in out:
        out.insert(0, w[0])
    return out


# -- the active window on KDE / Wayland: Capri's KWin watcher script ---------------------------------
# X11 can't see native Wayland windows, so on KDE we ask KWin itself: capri/kwin/capri-active is a small
# declarative script KWin runs, and it copies the active window (title, app id, frame box, stamp) into
# its own config file every time the focus changes. We just read that file.
_watch_cache: tuple = (None, None)


def _watch_files() -> list[str]:
    cfg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return [os.path.join(cfg, "kde.org", "kwin.conf"), os.path.join(cfg, "kwinrc")]  # Qt6 layout, old layout


def _watch_data():
    """(title, app id, (x, y, width, height) in scene pixels) from Capri's KWin watcher, None if it's not
    running. KWin stamps the file on load and on every focus change, so a file that's there means it's live."""
    global _watch_cache
    import configparser

    for path in _watch_files():
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if (path, mtime) == _watch_cache[:2]:
            return _watch_cache[2]
        try:
            cp = configparser.ConfigParser()
            cp.read(path)
            sect = cp["General"] if cp.has_section("General") else cp["CapriActive"]
            box = tuple(int(v) for v in sect.get("box", "").split())
            if len(box) != 4:
                continue
            data = (sect.get("title", ""), sect.get("app", ""), box)
        except Exception:
            continue
        _watch_cache = (path, mtime, data)
        return data
    _watch_cache = (None, None, None)
    return None


def ensure_watch() -> bool:
    """KDE Wayland: install / enable / load Capri's KWin watcher script so she can see the active window
    (X11 sees none of the native ones). Only does anything the first time, when no watcher data exists."""
    if not WAYLAND or not ("kde" in _desktop() or "plasma" in _desktop()):
        return False
    if _watch_data() is not None:
        return True
    tools = [shutil.which(t + "6") or shutil.which(t) for t in ("kpackagetool", "kwriteconfig", "qdbus")]
    if not all(tools):
        _hint("watch", "the active window on KDE Wayland needs KDE tools (Arch: sudo pacman -S kpackagetool "
                       "kwriteconfig qtdtools, they come with plasma-desktop)")
        return False
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kwin", "capri-active")

    def run(cmd) -> bool:
        try:
            return subprocess.run(cmd, timeout=30, capture_output=True).returncode == 0
        except Exception:
            return False

    kpackagetool, kwriteconfig, qdbus = tools
    if not (run([kpackagetool, "--type", "KWin/Script", "-i", src])
            or run([kpackagetool, "--type", "KWin/Script", "-u", src])):  # -u: an old copy is already in
        _hint("watch", "couldn't install Capri's KWin watcher script (capri/kwin/capri-active)")
        return False
    run([kwriteconfig, "--file", "kwinrc", "--group", "Plugins", "--key", "capri-activeEnabled", "true"])
    run([qdbus, "org.kde.KWin", "/KWin", "reconfigure"])
    end = time.monotonic() + 15  # KWin loads the script and stamps the file
    while time.monotonic() < end:
        if _watch_data() is not None:
            return True
        time.sleep(0.5)
    _hint("watch", "Capri's KWin watcher is installed but KWin never reported the active window; "
                   "log out and back in once if that keeps happening")
    return False


# -- eyes: screenshot + tesseract ------------------------------------------------------------------------
_warned: set[str] = set()


def _hint(key: str, text: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(f"[capri] eyes: {text}")


def _desktop() -> str:
    return os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def _wait_shot(path: str, timeout: float = 8.0) -> bool:
    """Spectacle can return before it has finished writing the PNG; wait for a non-empty file."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if os.path.getsize(path) > 0:
                return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def _tool_shot(active: bool, box=None):
    """A screenshot through a desktop's own tool (Wayland won't let X11 apps see other windows):
    Spectacle (KDE), grim (Hyprland, Sway and other wlroots desktops), gnome-screenshot (GNOME)."""
    from PIL import Image

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    desktop = _desktop()
    kde = "kde" in desktop or "plasma" in desktop
    gnome = "gnome" in desktop or "unity" in desktop
    tries = []

    def spectacle(active_window: bool) -> None:
        if shutil.which("spectacle"):
            # -i: a fresh instance, so an already-running Spectacle can't swallow the request via DBus
            tries.append(["spectacle", "-b", "-n", "-i", "-a" if active_window else "-f", "-o", path])

    def grim() -> None:
        if shutil.which("grim"):
            geo = f"{box[0]},{box[1]} {box[2] - box[0]}x{box[3] - box[1]}" if box else None
            tries.append(["grim", "-g", geo, path] if geo else ["grim", path])

    def gnome_shot(active_window: bool) -> None:
        if shutil.which("gnome-screenshot"):
            tries.append(["gnome-screenshot", "-w", "-f", path] if active_window else ["gnome-screenshot", "-f", path])

    if kde:
        # KWin doesn't implement wlr-screencopy, so grim always fails here; don't even try it.
        spectacle(active)
        if active:
            spectacle(False)  # her own window may be the active one: the whole screen still shows the app behind
        gnome_shot(active)
    elif gnome:
        gnome_shot(active)
        grim()
        spectacle(active)
    else:
        grim()
        spectacle(active)
        gnome_shot(active)

    try:
        for cmd in tries:
            try:
                result = subprocess.run(cmd, timeout=20, capture_output=True)
                if result.returncode == 0 and _wait_shot(path):
                    return Image.open(path).copy()
            except Exception:
                continue
        _hint("tool", "couldn't take a screenshot; on KDE Wayland install Spectacle (sudo pacman -S spectacle), "
                      "on Hyprland / Sway install grim, on GNOME install gnome-screenshot")
        return None
    finally:
        os.unlink(path)


def _x11_shot(box=None):
    from PIL import ImageGrab

    display = os.environ.get("DISPLAY") or None
    if WAYLAND and not display:
        return None
    try:
        # Pass the display explicitly: when xdisplay is None, Pillow 13 falls back to grim/spectacle, and its grim
        # fallback fails on KDE Wayland with a confusing CalledProcessError.
        img = ImageGrab.grab(bbox=box, xdisplay=display)
    except Exception as e:
        if not WAYLAND:  # on Wayland this is expected: XWayland can't read native windows
            _hint("x11", f"X11 screenshot failed: {e}")
        return None
    if img.getbbox() is None:  # all black: XWayland can't see native Wayland windows
        return None
    return img


def grab_active():
    """PIL image of the window you're in (None if it can't be had)."""
    box = active_box()
    if WAYLAND:
        img = _tool_shot(True, box)
        if img is not None:
            return img
    return _x11_shot(box) if box else None


def grab_screen():
    """PIL image of the whole screen (None if it can't be had)."""
    if WAYLAND:
        img = _tool_shot(False)
        if img is not None:
            return img
    return _x11_shot()


_TESS = {"en": "eng", "es": "spa", "pt": "por", "fr": "fra", "ru": "rus", "it": "ita", "de": "deu", "pl": "pol"}
_tess_langs: list = []


def _tess_have() -> set[str]:
    if not _tess_langs:
        try:
            r = subprocess.run(["tesseract", "--list-langs"], timeout=10, capture_output=True, text=True)
            _tess_langs.append({ln.strip() for ln in r.stdout.splitlines()[1:] if ln.strip()})
        except Exception:
            _tess_langs.append(set())
    return _tess_langs[0]


def ocr_lines(img, lang: str = "en") -> list[tuple[str, float, float]]:
    """Lines of text in an image with their height and top y, via the tesseract command, in the user's language
    (plus English) when its language data is installed."""
    if not shutil.which("tesseract"):
        _hint("ocr", "reading text needs tesseract (Arch: sudo pacman -S tesseract tesseract-data-eng, "
                     "Kali / Debian: sudo apt install tesseract-ocr)")
        return []
    have = _tess_have()
    want = _TESS.get(lang, "eng")
    if want != "eng" and want not in have:
        _hint("ocr-" + want, f"to read {want} text on screen: Arch: sudo pacman -S tesseract-data-{want}, "
                             f"Kali / Debian: sudo apt install tesseract-ocr-{want}")
    codes = "+".join(c for c in dict.fromkeys([want, "eng"]) if c in have or not have) or "eng"
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(path)
        r = subprocess.run(["tesseract", path, "-", "-l", codes, "--psm", "3", "tsv"], timeout=25,
                           capture_output=True, text=True)
    finally:
        os.unlink(path)
    lines: dict = {}  # (block, par, line) -> [words, max height, top]
    for row in r.stdout.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5" or not c[11].strip():
            continue
        key = (c[2], c[3], c[4])
        top, h = float(c[7]), float(c[9])
        ln = lines.setdefault(key, [[], 0.0, top])
        ln[0].append(c[11].strip())
        ln[1] = max(ln[1], h)
        ln[2] = min(ln[2], top)
    return sorted(((" ".join(w), h, y) for w, h, y in lines.values()), key=lambda t: t[2])


def ocr(img) -> list[str]:
    """Lines of text in an image (English), via tesseract."""
    return [t for t, _, _ in ocr_lines(img, "en")]


def open_path(target: str) -> bool:
    exe = shutil.which("xdg-open")
    if not exe:
        return False
    subprocess.Popen([exe, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return True


def media(action: str) -> str:
    """Play/pause/next/previous through MPRIS (Spotify, browsers, most players)."""
    if not shutil.which("playerctl"):
        return "media controls need playerctl (sudo pacman -S playerctl)"
    cmd = {"pause": "pause", "resume": "play", "next": "next", "previous": "previous"}.get(action)
    if cmd is None:
        return f"unknown action {action}"
    subprocess.run(["playerctl", cmd], timeout=5, capture_output=True)
    return f"sent {action}"

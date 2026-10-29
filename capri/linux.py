"""Linux stand-ins for the Windows bits: keys held down, idle time, open windows and their titles, screenshots.

Keys and idle come straight from the kernel (/dev/input/event*), which works on X11 and Wayland alike but needs
the user in the `input` group; without it they fall back to X11. Windows come from X11 (python-xlib). Capri runs
through XWayland on Wayland desktops (capri_dev.py sets QT_QPA_PLATFORM=xcb) because Wayland won't let an app put
its own windows where it wants; there she only sees other X11 / XWayland windows.
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
    d = _display()
    if d is None:
        return ""
    try:
        wid = (_prop(d.screen().root, "_NET_ACTIVE_WINDOW") or [0])[0]
        return _title(d.create_resource_object("window", wid)) if wid else ""
    except Exception:
        return ""


def active_box():
    d = _display()
    if d is None:
        return None
    wid = (_prop(d.screen().root, "_NET_ACTIVE_WINDOW") or [0])[0]
    hit = window_box(wid) if wid else None
    return hit[0] if hit else None


def titles() -> list[str]:
    return [t for _, _, t, _ in windows() if t]


# -- eyes: screenshot + tesseract ------------------------------------------------------------------------
def grab_active():
    """PIL image of the window you're in: Spectacle on KDE Wayland (X11 can't see Wayland windows), else X11."""
    from PIL import Image, ImageGrab

    if WAYLAND and shutil.which("spectacle"):
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            subprocess.run(["spectacle", "-b", "-n", "-a", "-o", path], timeout=10, capture_output=True)
            return Image.open(path).copy() if os.path.getsize(path) else None
        finally:
            os.unlink(path)
    box = active_box()
    if not box:
        return None
    return ImageGrab.grab(bbox=box, xdisplay=None)


def ocr(img) -> list[str]:
    """Lines of text in an image, via the tesseract command (sudo pacman -S tesseract tesseract-data-eng)."""
    if not shutil.which("tesseract"):
        return []
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(path)
        r = subprocess.run(["tesseract", path, "-", "-l", "eng", "--psm", "3"], timeout=20, capture_output=True,
                           text=True)
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    finally:
        os.unlink(path)


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

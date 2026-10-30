"""Her skins: the registry, the saved pick, every skin's sprite sheets, and the watcher who never talks.
Run with: python -m pytest tests  (offscreen Qt: no windows, no audio, no model)."""
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from capri import skins
from capri.desk import settings as settings_mod
from capri.desk.app import DeskApp
from capri.desk.capri import Capri
from capri.desk.sprites import CLIPS, SPRITES, Sprites


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def pump(ms=50):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QCoreApplication.processEvents()


# -- registry ---------------------------------------------------------------------------
def test_registry():
    ids = [s.id for s in skins.SKINS]
    assert len(ids) == len(set(ids))
    assert skins.get(skins.DEFAULT).id == "capri"
    assert skins.get("nope").id == "capri" and skins.get("").id == "capri" and skins.get(None).id == "capri"
    assert skins.get("classic").folder == SPRITES
    assert skins.get("capri").can_talk and skins.get("classic").can_talk
    assert not skins.get("watcher").can_talk


def test_secret_label():
    w = skins.get("watcher")
    assert skins.label(w, []) == "???"
    assert skins.label(w, ["watcher"]) == "Watcher"
    assert skins.label(skins.get("capri"), []) == "Capri"


# -- every skin is a drop-in copy of the classic sheets: same names, sizes, frame layout -----------
@pytest.mark.parametrize("skin", [s for s in skins.SKINS if s.folder != SPRITES], ids=lambda s: s.id)
def test_skin_sheets_match_classic(qapp, skin):
    for name in CLIPS:
        new, old = QImage(str(skin.folder / f"{name}.png")), QImage(str(SPRITES / f"{name}.png"))
        assert not new.isNull(), f"{skin.id}/{name}.png missing"
        assert (new.width(), new.height()) == (old.width(), old.height()), name
        assert new.hasAlphaChannel(), name
    sp = Sprites(240, 1.0, skin.folder)
    assert sp.palette and all(sp[n].count == CLIPS[n][0] for n in CLIPS)


# -- the saved pick ---------------------------------------------------------------------
def test_settings_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "DATA", tmp_path)
    cfg = {"desk": {"dj": False, "vibe": True, "eyes": True, "chatter": True}, "stt": {"mode": "hold", "talk_key": "ctrl+1"}}
    s = settings_mod.Settings(cfg)
    assert s["skin"] == "capri" and s["skins_seen"] == []
    s.set("skin", "watcher")
    s.set("skins_seen", ["watcher"])
    again = settings_mod.Settings(cfg)
    assert again["skin"] == "watcher" and again["skins_seen"] == ["watcher"]


# -- the watcher: no chat, no voice, nothing heard, no brain -----------------------------
def watcher_capri():
    bubble = SimpleNamespace(calls=[])
    for name in ("say", "think", "listen", "open_input", "close_bubble", "place", "append"):
        setattr(bubble, name, lambda *a, n=name, **k: bubble.calls.append(n))
    bubble.typing = False
    return SimpleNamespace(skin=skins.get("watcher"), can_talk=False, bubble=bubble, mode="stand", voice=None,
                           blips=True, speaking=False, now=0.0, next_roam=0.0, last_touch=0.0, on_user=None,
                           sfx=SimpleNamespace(play=lambda *a: None))


def test_watcher_never_talks(qapp):
    c = watcher_capri()
    c.voice = lambda *a: pytest.fail("watcher used her voice")
    c.on_user = lambda line: pytest.fail("watcher sent a line to her brain")
    done = []
    Capri.say(c, "hello", done=lambda: done.append(1))
    Capri.say_more(c, "more")
    Capri.heard(c, "hey capri")
    Capri.listening(c, True)
    Capri.click(c)
    pump()
    assert done == [1]  # quitting waits on this: it still runs
    assert not c.speaking
    assert c.bubble.calls == []  # no bubble, no chat box, no REC dot


def test_watcher_app_blocks_brain_and_chatter(qapp):
    agent = SimpleNamespace(respond=lambda *a, **k: pytest.fail("LLM called"))
    capri = watcher_capri()
    capri.say = lambda *a, **k: pytest.fail("watcher spoke")
    app = SimpleNamespace(capri=capri, agent=agent, busy=None, ears=None, last_talk=0.0)
    DeskApp.on_user(app, "hi")
    assert DeskApp._own(app, lambda: pytest.fail("LLM called")) is False
    DeskApp._watch(app)  # returns before reading the screen or asking the brain anything
    DeskApp._replied(app, "reminder!", "", False)
    DeskApp._part(app, "part", "", True)


def test_watcher_mutes_ears(qapp):
    ears = SimpleNamespace(muted=False)
    capri = SimpleNamespace(set_skin=lambda sid: None)
    store = type("Store", (dict,), {"set": dict.__setitem__})  # Settings without the file
    app = SimpleNamespace(s=store(skin="capri", skins_seen=[]), capri=capri, ears=ears, _wake_up=lambda: None)
    DeskApp.set_skin(app, "watcher")
    assert ears.muted and app.s["skin"] == "watcher" and app.s["skins_seen"] == ["watcher"]
    DeskApp.set_skin(app, "capri")
    assert not ears.muted and app.s["skin"] == "capri"

"""Capri Live (live.bat): connects to your TikTok LIVE chat by username (no login), shows it colour-coded and saves
every comment to data/live_chat.jsonl, where Capri picks the questions she answers. Ideas from chat land on the
ideas board, a notepad window you can show on stream.

Colours in the feed: green = a question she might answer, pink = yams, cyan = an idea, grey = skipped,
a star = she answered it. "Mock chat" fills it with fake comments so you can set things up without going live.
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
import threading
import time
import uuid

from PySide6.QtCore import QFileSystemWatcher, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ..config import DATA, ROOT
from . import mock
from .pick import ANSWERED, CHAT, IDEAS, Comment, add_idea, kind

SETTINGS = DATA / "live.json"
STREAMS = DATA / "streams"  # one file per session: every comment and every answer, for picking training data later
STARRED = STREAMS / "starred.jsonl"  # what you double-clicked as good
FONT = ROOT / "assets" / "desk" / "fonts" / "ShareTechMono-Regular.ttf"
COLORS = {"question": "#2bff9a", "yams": "#ff2a6d", "idea": "#78faff", "": "#6f6080"}
STYLE = """
QWidget { background: #0e0616; color: #f6f0fa; }
QLineEdit { background: #1d0c2b; border: 1px solid #ff1460; padding: 6px; selection-background-color: #ff1460; }
QPushButton { background: #ff1460; color: black; border: none; padding: 7px 14px; font-weight: bold; }
QPushButton:hover { background: #2bff9a; }
QPushButton:disabled { background: #3a2246; color: #806a90; }
QListWidget { background: #08030d; border: 1px solid #3a1c4a; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #ff1460; }
QCheckBox::indicator:checked { background: #2bff9a; }
QPlainTextEdit { background: #08030d; border: 2px solid #ff1460; padding: 10px; selection-background-color: #ff1460; }
"""


def font(px: int) -> QFont:
    fid = QFontDatabase.addApplicationFont(str(FONT))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    f = QFont(fams[0] if fams else "Consolas")
    f.setPixelSize(px)
    return f


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(d: dict) -> None:
    DATA.mkdir(exist_ok=True)
    SETTINGS.write_text(json.dumps(d, indent=2), encoding="utf-8")


class Signals(QObject):
    comment = Signal(str, str, str, object)  # nick, @handle, text, {"club": level, "top": bool}
    gift = Signal(str, str, str, int)  # nick, @handle, gift name, diamonds
    status = Signal(str)
    done = Signal()
    followers = Signal(int)


class TikTok:
    """TikTokLive in its own thread and asyncio loop; everything it hears goes out through Qt signals."""

    def __init__(self, sig: Signals):
        self.sig = sig
        self.client = None
        self.loop = None

    def start(self, username: str):
        threading.Thread(target=self._run, args=(username,), daemon=True).start()

    def _run(self, username: str):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, GiftEvent, LiveEndEvent, RoomPinEvent

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        client = self.client = TikTokLiveClient(unique_id="@" + username.lstrip("@"))

        @client.on(ConnectEvent)
        async def _connected(_):
            self.sig.status.emit(f"connected to @{username.lstrip('@')}'s LIVE")

        @client.on(CommentEvent)
        async def _comment(e: CommentEvent):
            u = e.user
            self.sig.comment.emit(getattr(u, "nickname", "") or "", getattr(u, "unique_id", "") or "", e.content or "",
                                  supporter(u))

        @client.on(RoomPinEvent)
        async def _pinned(e: RoomPinEvent):
            """A mod pinned a comment: she reads it next."""
            try:
                m = e.chat_message
                if m is None or "unpin" in (getattr(e, "method", "") or "").lower():
                    return
                u = m.user
                text = getattr(m, "comment", "") or getattr(m, "content", "") or ""
                if text:
                    self.sig.comment.emit(getattr(u, "nickname", "") or "", getattr(u, "unique_id", "") or "", text,
                                          dict(supporter(u), pinned=True))
            except Exception as ex:
                print(f"[live] pin skipped: {ex}")

        @client.on(GiftEvent)
        async def _gift(e: GiftEvent):
            try:
                if e.streaking or e.gift is None:  # a combo still going: count it once, when it ends
                    return
                diamonds = int(e.repeat_count or 1) * int(e.gift.diamond_count or 0)
                u = e.user
                self.sig.gift.emit(getattr(u, "nickname", "") or "", getattr(u, "unique_id", "") or "",
                                   getattr(e.gift, "name", "") or "gift", diamonds)
            except Exception as ex:
                print(f"[live] gift skipped: {ex}")

        @client.on(LiveEndEvent)
        async def _ended(_):
            self.sig.status.emit("the LIVE ended")

        @client.on(DisconnectEvent)
        async def _gone(_):
            self.sig.status.emit("disconnected")

        try:
            self.sig.status.emit(f"connecting to @{username.lstrip('@')} ...")
            self.loop.run_until_complete(client.connect())
        except Exception as e:
            name = type(e).__name__
            if "Offline" in name:
                self.sig.status.emit(f"@{username.lstrip('@')} isn't live right now. Go live, then hit Connect.")
            elif "NotFound" in name:
                self.sig.status.emit(f"no TikTok account called @{username.lstrip('@')}")
            else:
                self.sig.status.emit(f"couldn't connect: {name}: {e}"[:160])
        finally:
            self.sig.done.emit()

    def stop(self):
        if self.client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)


def supporter(u) -> dict:
    """Fan club level (their club badge in your LIVE) and top-gifter badge of whoever commented."""
    out = {"club": 0, "top": False}
    try:
        out["club"] = int(getattr(u, "member_level", None) or 0)
        if not out["club"]:
            fc = getattr(getattr(u, "fans_club", None), "data", None)
            out["club"] = int(getattr(fc, "level", 0) or 0)
        out["top"] = bool(getattr(u, "is_top_gifter", False))
    except Exception:
        pass
    return out


def fetch_followers(username: str) -> int | None:
    """Follower count of a TikTok account, live or not (the same public endpoint TikTokLive uses to find the room)."""
    try:
        from TikTokLive.client.web.routes.fetch_room_id_api import FetchRoomIdAPIRoute
        from TikTokLive.client.web.web_client import TikTokWebClient

        async def get():
            web = TikTokWebClient()
            try:
                return await FetchRoomIdAPIRoute.fetch_user_room_data(web, username.lstrip("@"))
            finally:
                try:
                    await web.close()
                except Exception:
                    pass

        loop = asyncio.new_event_loop()
        try:
            data = loop.run_until_complete(get())
        finally:
            loop.close()
        stats = (data.get("data") or {}).get("stats") or {}
        n = stats.get("followerCount")
        return int(n) if n is not None else None
    except Exception as e:
        print(f"[live] couldn't get the follower count: {type(e).__name__}: {e}")
        return None


class IdeasBoard(QWidget):
    """The notepad: big, readable, saved as you type (data/ideas.md). Ideas from chat appear in it by themselves."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Capri Ideas")
        self.setWindowIcon(QIcon(str(ROOT / "assets" / "icons" / "capri.png")))
        self.setStyleSheet(STYLE)
        self.resize(520, 640)
        title = QLabel("// CAPRI IDEAS BOARD")
        title.setFont(font(22))
        title.setStyleSheet("color: #ff1460; padding: 4px 2px;")
        hint = QLabel("drop ideas in chat with !idea ... or tell Capri \"note this idea\"")
        hint.setFont(font(13))
        hint.setStyleSheet("color: #78faff;")
        self.edit = QPlainTextEdit()
        self.edit.setFont(font(18))
        lay = QVBoxLayout(self)
        lay.addWidget(title)
        lay.addWidget(hint)
        lay.addWidget(self.edit)
        self._saved = ""
        self._load()
        self.save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save)
        self.edit.textChanged.connect(self.save_timer.start)
        self.watch = QFileSystemWatcher(self)
        self._watch()
        self.watch.fileChanged.connect(lambda _: QTimer.singleShot(150, self._changed))
        self.watch.directoryChanged.connect(lambda _: QTimer.singleShot(150, self._changed))

    def _watch(self):
        DATA.mkdir(exist_ok=True)
        if not IDEAS.exists():
            IDEAS.write_text("## Ideas\n", encoding="utf-8")
        for p in (str(IDEAS), str(DATA)):
            if p not in self.watch.files() + self.watch.directories():
                self.watch.addPath(p)

    def _load(self):
        try:
            text = IDEAS.read_text(encoding="utf-8")
        except OSError:
            text = "## Ideas\n"
        self._saved = text
        bar = self.edit.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        cur = self.edit.textCursor().position()
        self.edit.blockSignals(True)
        self.edit.setPlainText(text)
        self.edit.blockSignals(False)
        c = self.edit.textCursor()
        c.setPosition(min(cur, len(text)))
        self.edit.setTextCursor(c)
        if at_end:
            bar.setValue(bar.maximum())

    def _changed(self):
        self._watch()
        try:
            disk = IDEAS.read_text(encoding="utf-8")
        except OSError:
            return
        if disk != self._saved and self.edit.toPlainText() == self._saved:  # changed elsewhere, nothing unsaved here
            self._load()

    def _save(self):
        text = self.edit.toPlainText()
        if text != self._saved:
            self._saved = text
            IDEAS.write_text(text, encoding="utf-8")


class LiveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Capri Live")
        self.setWindowIcon(QIcon(str(ROOT / "assets" / "icons" / "capri.png")))
        self.setStyleSheet(STYLE)
        self.resize(560, 700)
        self.s = load_settings()
        self.sig = Signals()
        self.sig.comment.connect(self.on_comment)
        self.sig.gift.connect(self.on_gift)
        self.gifts: dict[str, int] = {}  # @handle -> diamonds sent this session
        self.sig.status.connect(self.set_status)
        self.sig.done.connect(self._disconnected)
        self.sig.followers.connect(self._got_followers)
        self.tiktok = None
        STREAMS.mkdir(parents=True, exist_ok=True)
        self.archive = STREAMS / time.strftime("%Y-%m-%d_%H%M.jsonl")
        self.items: dict[str, QListWidgetItem] = {}
        self.records: dict[int, dict] = {}  # feed row -> what it was, for starring
        self.counts = {"question": 0, "yams": 0, "idea": 0, "": 0}
        self.ideas_seen: set[str] = set()

        title = QLabel("// CAPRI LIVE")
        title.setFont(font(24))
        title.setStyleSheet("color: #ff1460;")
        self.user = QLineEdit(self.s.get("username", ""))
        self.user.setPlaceholderText("your TikTok username (e.g. hibura)")
        self.user.setFont(font(15))
        self.user.returnPressed.connect(self.connect_live)
        self.go = QPushButton("Connect")
        self.go.clicked.connect(self.toggle)
        row = QHBoxLayout()
        at = QLabel("@")
        at.setFont(font(18))
        row.addWidget(at)
        row.addWidget(self.user, 1)
        row.addWidget(self.go)
        self.mock = QCheckBox("Mock chat (fake comments, for testing)")
        self.mock.setFont(font(13))
        self.mock.toggled.connect(self.toggle_mock)
        self.answer = QCheckBox("Capri answers chat (needs her Stream mode on)")
        self.answer.setFont(font(13))
        self.answer.setChecked(self.s.get("answer", True))
        self.answer.toggled.connect(self._save_answer)
        self.status = QLabel("not connected")
        self.status.setFont(font(13))
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #78faff;")
        self.feed = QListWidget()
        self.feed.setFont(font(14))
        self.feed.setWordWrap(True)
        self.feed.setToolTip("Double-click a line to star it: starred chat and answers are saved for training her")
        self.feed.itemDoubleClicked.connect(self._star)
        self.fans = QLabel("followers: ...")
        self.fans.setFont(font(15))
        self.fans.setStyleSheet("color: #2bff9a;")
        self.tally = QLabel()
        self.tally.setFont(font(12))
        self.tally.setStyleSheet("color: #a896b8;")
        ideas = QPushButton("Open ideas board")
        ideas.clicked.connect(self.show_ideas)
        bottom = QHBoxLayout()
        bottom.addWidget(self.tally, 1)
        bottom.addWidget(ideas)
        lay = QVBoxLayout(self)
        lay.addWidget(title)
        lay.addLayout(row)
        lay.addWidget(self.mock)
        lay.addWidget(self.answer)
        lay.addWidget(self.status)
        lay.addWidget(self.fans)
        lay.addWidget(self.feed, 1)
        lay.addLayout(bottom)

        self.board = IdeasBoard()
        self.mock_timer = QTimer(self, singleShot=True, timeout=self._mock_one)
        self.marks = QTimer(self, interval=1500, timeout=self._mark_answered)
        self.marks.start()
        self._answered_pos = ANSWERED.stat().st_size if ANSWERED.exists() else 0
        self._tally()
        self._save_answer(self.answer.isChecked())
        self.fan_timer = QTimer(self, interval=5 * 60 * 1000, timeout=self.refresh_followers)
        self.fan_timer.start()
        self.refresh_followers()
        if not self.user.text():
            QTimer.singleShot(0, self.user.setFocus)

    # -- followers (she knows the real number) -------------------------------------------
    def refresh_followers(self):
        name = (self.s.get("username") or self.user.text()).strip().lstrip("@")
        if not name:
            return

        def work():
            n = fetch_followers(name)
            if n is not None:
                self.sig.followers.emit(n)

        threading.Thread(target=work, daemon=True).start()

    def _got_followers(self, n: int):
        self.fans.setText(f"followers: {n:,}  (@{self.s.get('username', '')})")
        s = load_settings()  # the file Capri reads; keep what's there
        s.update(self.s)
        s["followers"], s["followers_at"] = n, time.time()
        self.s = s
        save_settings(s)
        print(f"[live] @{s.get('username')} has {n} followers")

    # -- connecting ---------------------------------------------------------------------
    def toggle(self):
        if self.tiktok:
            self.tiktok.stop()
            self.set_status("disconnecting ...")
        else:
            self.connect_live()

    def connect_live(self):
        name = self.user.text().strip().lstrip("@")
        if not name or self.tiktok:
            return
        self.s["username"] = name
        save_settings(self.s)
        self.refresh_followers()
        self.tiktok = TikTok(self.sig)
        self.tiktok.start(name)
        self.go.setText("Disconnect")
        self.user.setEnabled(False)

    def _disconnected(self):
        self.tiktok = None
        self.go.setText("Connect")
        self.user.setEnabled(True)

    def set_status(self, text: str):
        self.status.setText(text)
        print(f"[live] {text}")

    def toggle_mock(self, on: bool):
        if on:
            self._mock_one()
        else:
            self.mock_timer.stop()

    def _mock_one(self):
        if random.random() < 0.08:
            self.on_gift(*mock.gift())
        elif random.random() < 0.05:  # a mod pins a question
            nick, handle, text = mock.comment(pool="questions")
            self.on_comment(nick, handle, text, dict(mock.badges(handle), pinned=True))
        else:
            nick, handle, text = mock.comment()
            self.on_comment(nick, handle, text, mock.badges(handle))
        self.mock_timer.start(int(random.uniform(1.2, 4.5) * 1000))

    def _save_answer(self, on: bool):
        self.s["answer"] = bool(on)
        save_settings(self.s)

    # -- chat -----------------------------------------------------------------------------
    def on_gift(self, nick: str, handle: str, name: str, diamonds: int):
        key = (handle or nick).lower()
        self.gifts[key] = self.gifts.get(key, 0) + diamonds
        rec = {"kind": "gift", "t": time.time(), "nick": nick, "user": handle, "gift": name, "diamonds": diamonds,
               "mock": self.mock.isChecked()}
        try:
            self._archive(rec)
        except OSError:
            pass
        item = QListWidgetItem(f"$ {nick} sent {name} ({diamonds:,} diamonds, {self.gifts[key]:,} this stream)")
        item.setForeground(QColor("#ffe14d"))
        self._add(item, rec)

    def on_comment(self, nick: str, handle: str, text: str, meta=None):
        meta = meta or {}
        gifts = self.gifts.get((handle or nick).lower(), 0)
        c = Comment(uuid.uuid4().hex[:12], nick, handle, " ".join(text.split()), time.time(),
                    int(meta.get("club") or 0), gifts, bool(meta.get("top")), bool(meta.get("pinned")))
        k = kind(c, self.s.get("username", ""))
        self.counts[k] += 1
        rec = {"kind": "comment", "id": c.id, "t": c.t, "nick": nick, "user": handle, "text": c.text,
               "club": c.club, "gifts": c.gifts, "top": c.top, "pinned": c.pinned, "mock": self.mock.isChecked()}
        try:
            DATA.mkdir(exist_ok=True)
            with CHAT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._archive(dict(rec, filter=k or "skip"))
        except OSError as e:
            self.set_status(f"couldn't save chat: {e}")
        if k == "idea":
            key = c.text.lower()
            if key not in self.ideas_seen:
                self.ideas_seen.add(key)
                idea = c.text.split("!idea", 1)[-1].strip(" :-") if c.text.lower().startswith("!idea") else c.text
                add_idea(idea, "@" + (handle or nick))
        tag = "PIN" if c.pinned else {"question": "?", "yams": "Y", "idea": "+", "": " "}[k]
        badges = "".join([f"[club {c.club}]" if c.club else "", f"[{c.gifts:,} dia]" if c.gifts else "",
                          "[top gifter]" if c.top and not c.gifts else ""])
        item = QListWidgetItem(f"{tag} {badges + ' ' if badges else ''}{nick}: {c.text}")
        item.setForeground(QColor("#ff1460" if c.pinned else COLORS[k]))
        self._add(item, rec)
        self.items[c.id] = item
        self._tally()

    def _add(self, item: QListWidgetItem, rec: dict, after: QListWidgetItem | None = None):
        if after is not None and self.feed.row(after) >= 0:
            self.feed.insertItem(self.feed.row(after) + 1, item)
        else:
            self.feed.addItem(item)
        self.records[id(item)] = rec
        while self.feed.count() > 400:
            old = self.feed.takeItem(0)
            self.records.pop(id(old), None)
            self.items = {i: it for i, it in self.items.items() if it is not old}
        self.feed.scrollToBottom()

    def _archive(self, rec: dict):
        with self.archive.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _star(self, item: QListWidgetItem):
        """Double-click: star (or unstar) a comment or one of her answers, saved for training her later."""
        rec = self.records.get(id(item))
        if not rec:
            return
        on = not item.text().startswith("[*]")
        item.setText(("[*] " + item.text()) if on else item.text()[4:])
        STREAMS.mkdir(parents=True, exist_ok=True)
        with STARRED.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(rec, starred=on, starred_at=time.time()), ensure_ascii=False) + "\n")

    def _mark_answered(self):
        try:
            size = ANSWERED.stat().st_size
        except OSError:
            return
        if size < self._answered_pos:
            self._answered_pos = 0
        if size == self._answered_pos:
            return
        with ANSWERED.open("rb") as f:
            f.seek(self._answered_pos)
            data = f.read()
        self._answered_pos = size
        for line in data.decode("utf-8", "ignore").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            item = self.items.get(d.get("id"))
            if item:
                item.setText("* " + item.text()[2:])
                item.setForeground(QColor("#ffe14d"))
            if d.get("reply"):
                rec = {"kind": "capri", "t": d.get("t"), "to_id": d.get("id"), "question": d.get("q", ""),
                       "who": d.get("who", ""), "reply": d["reply"], "yams": d.get("yams", False)}
                self._archive(rec)
                answer = QListWidgetItem(f"    Capri: {d['reply']}")
                answer.setForeground(QColor("#ff6fd8"))
                self._add(answer, rec, after=item)

    def _tally(self):
        c = self.counts
        self.tally.setText(f"questions {c['question']}  ·  yams {c['yams']}  ·  ideas {c['idea']}  ·  skipped {c['']}")

    def show_ideas(self):
        self.board.show()
        self.board.raise_()

    def closeEvent(self, e):
        if self.tiktok:
            self.tiktok.stop()
        self.board.close()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    w = LiveWindow()
    w.show()
    if "--mock" in sys.argv:
        w.mock.setChecked(True)
    if "--ideas" in sys.argv:
        w.show_ideas()
    sys.exit(app.exec())

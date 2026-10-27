"""Which live-chat comments Capri may answer. Code rules first (cheap, strict): only real questions, nothing rude,
sexual, creepy, private, spammy or full of links. Her brain then picks the single best one out of what's left.

Comments asking for her "yams" skip the question rule: those get trolled on purpose.
Suggestions ("you should add...", "!idea ...") go to the ideas board instead of being answered.
Pinned comments (your mods pin them to help her) skip the line: she reads those next, no picking, no cooldowns.
"""
from __future__ import annotations

import json
import math
import random
import re
import time
from dataclasses import dataclass, field

from ..config import DATA

CHAT = DATA / "live_chat.jsonl"  # every comment, written by the chat app
ANSWERED = DATA / "live_answered.jsonl"  # the ones she answered (the chat app marks them)
IDEAS = DATA / "ideas.md"  # the ideas board

QUESTION_START = re.compile(
    r"^(?:(?:hey|yo|hi|hello|ok|okay|so|wait|bro|capri|campy)[,!.\s]+)*"
    r"(?:what|what's|whats|why|how|who|who's|whos|where|when|which|can|could|do|does|did|is|are|will|would|should|"
    r"have|has|ever|wanna|u|r|ur|rate|roast|tell (?:me|us)|guess|describe|explain|sing|say hi)\b", re.I)
YAMS = re.compile(r"\by+a+m+[sz]+\b|\byam+(?:ie|y)s?\b|\byammers\b", re.I)
IDEA = re.compile(r"^\s*!idea\b|\b(?:you should (?:add|make|let|give)|she should|capri should|(?:can|could) you (?:add|make|give) "
                  r"(?:her|capri)|make her|give her|add (?:a|an) |idea:|suggestion:?|feature (?:idea|request))", re.I)

# never answered, whatever the brain thinks: sexual, slurs, hate, violence, self-harm, private info, drama
_BLOCK = re.compile(
    r"\b(?:sex\w*|porn\w*|nude\w*|naked|nsfw|horny|boob\w*|tits?|titties|ass(?:es)?|booty|thicc|feet pics?|onlyfans|"
    r"dick\w*|cock|pussy|cum|kiss me|marry me|daddy|mommy|step ?(?:sis|bro)|"
    r"n[i1!]gg\w*|f[a@]gg?\w*|retard\w*|tr[a@]nn\w*|k[i1]ke|ch[i1]nk|sp[i1]c|[a-z] ?word|slurs?|swear\w*|cuss\w*|"
    r"bad words?|racist\w*|"
    r"kill (?:your|ur|my)self|kys|suicide|self ?harm|cut (?:my|your)self|die|rape\w*|nazi\w*|hitler|terroris\w*|"
    r"shoot(?:ing)? up|bomb\w*|gun\w* down|"
    r"address|where\b.{0,20}\blives?|phone (?:number|#)|real name|ip ?address|dox\w*|password|"
    r"credit card|how much (?:money|does|do)\b.{0,20}\b(?:make|earn)|salary|income|how old is (?:he|hibura)|"
    r"face reveal|what (?:does|do) (?:he|hibura) look like|"
    r"trump|biden|democrat\w*|republican\w*|israel\w*|palestin\w*|religion|allah|jesus|"
    r"fuck\w*|f\*+k|shit\w*|bitch\w*|whore|slut\w*|stfu|gtfo|cunt|bastard|"
    r"ugly|fat|stupid|dumb|idiot|loser|cringe|trash|garbage|mid|boring|"
    r"follow (?:me|back)|f4f|sub4sub|check (?:out )?my|my (?:page|channel|profile))\b", re.I)
_LINK = re.compile(r"https?://|www\.|\.(?:com|net|org|gg|ly|io|tv|xyz)\b|discord\.gg", re.I)
_DIGITS = re.compile(r"\d[\d\s\-().]{6,}\d")
_SPAM = re.compile(r"(.)\1{5,}|(\b\w+\b)(?:\W+\2\b){3,}", re.I)


@dataclass
class Comment:
    id: str
    nick: str  # display name ("Neon Kid")
    user: str  # @handle
    text: str
    t: float = field(default_factory=time.time)
    club: int = 0  # their level in Hibura's TikTok fan club (0 = not in it)
    gifts: int = 0  # diamonds they've sent this stream
    top: bool = False  # top gifter badge
    pinned: bool = False  # a mod pinned it in the LIVE: she reads it next

    @property
    def boost(self) -> float:
        """How much more likely she is to pick them: 1 for anyone, more for fan club levels and gifts.
        Club level 10 ~ 2.5x, 1,000 diamonds ~ 4.5x, both ~ 6x."""
        return (1 + min(self.club, 40) * 0.15 + math.log2(1 + max(0, self.gifts)) * 0.35
                + (1.0 if self.top else 0.0))

    @property
    def supporter(self) -> str:
        """'in the fan club (level 12), sent 300 diamonds' or '' for everyone else."""
        bits = []
        if self.club:
            bits.append(f"in Hibura's fan club (level {self.club})")
        if self.gifts:
            bits.append(f"sent {self.gifts:,} diamonds in gifts this stream")
        elif self.top:
            bits.append("one of the top gifters")
        return ", ".join(bits)

    @property
    def who(self) -> str:
        """The name she says out loud: their display name if it's readable, else their handle, else nothing."""
        for name in (self.nick, self.user):
            name = re.sub(r"[^\w .'-]", "", name or "").strip()
            if 2 <= len(name) <= 20 and re.search(r"[a-z]", name, re.I) and not re.fullmatch(r"user\d{5,}", name, re.I):
                return name
        return ""


def kind(c: Comment, me: str = "") -> str:
    """'yams', 'idea', 'question' or '' (ignore). `me` = the streamer's own handle: they talk to her by voice."""
    text = " ".join((c.text or "").split())
    if not text or (me and c.user.lstrip("@").lower() == me.lstrip("@").lower()):
        return ""
    if YAMS.search(text):
        return "yams"
    if _LINK.search(text) or _DIGITS.search(text) or _SPAM.search(text) or _BLOCK.search(text):
        return ""
    if IDEA.search(text) and len(text) >= 10:
        return "idea"
    letters = re.sub(r"[^a-z]", "", text.lower())
    if len(letters) < 8 or len(text) > 200 or len(text.split()) < 3 or len(text.split()) > 35:
        return ""
    if len(letters) < 0.5 * len(re.sub(r"\s", "", text)):  # mostly emojis / symbols
        return ""
    caps = re.sub(r"[^A-Za-z]", "", text)
    if len(caps) > 12 and sum(ch.isupper() for ch in caps) > 0.7 * len(caps):  # SHOUTING
        return ""
    if "?" in text or QUESTION_START.search(text):
        return "question"
    return ""


class Pool:
    """Recent chat, filtered: what she could answer next. One answer per viewer every few minutes, nothing twice."""

    def __init__(self, me: str = "", keep: float = 180.0, per_user: float = 300.0):
        self.me, self.keep, self.per_user = me, keep, per_user
        self.questions: list[Comment] = []
        self.yams: list[Comment] = []
        self.ideas: list[Comment] = []
        self.answered_users: dict[str, float] = {}
        self.answered_texts: set[str] = set()
        self.last_yams = 0.0
        self.yams_answers = 0
        self.pinned: list[Comment] = []
        self.seen: list[float] = []  # when comments came in (how busy chat is)

    def add(self, c: Comment) -> str:
        self.seen = [t for t in self.seen if c.t - t < 120] + [c.t]
        if c.pinned:
            text = " ".join((c.text or "").split())
            if (text and _norm(text) not in self.answered_texts and not any(_norm(p.text) == _norm(text) for p in self.pinned)
                    and not (_BLOCK.search(text) or _LINK.search(text) or _DIGITS.search(text))):
                self.pinned.append(c)
                return "pinned"
            return ""
        k = kind(c, self.me)
        if k == "question" and _norm(c.text) not in self.answered_texts:
            self.questions.append(c)
        elif k == "yams":
            self.yams.append(c)
        elif k == "idea":
            self.ideas.append(c)
        return k

    def _fresh(self, now: float):
        self.questions = [c for c in self.questions if now - c.t < self.keep][-40:]
        self.yams = [c for c in self.yams if now - c.t < 60][-10:]

    def busyness(self, now: float | None = None) -> float:
        """0 = dead quiet chat, 1 = busy (25+ comments a minute)."""
        now = now or time.time()
        return min(1.0, len([t for t in self.seen if now - t < 120]) / 2 / 25)

    def pinned_next(self, now: float | None = None) -> Comment | None:
        """The oldest pinned comment still waiting (pins older than 10 minutes are dropped)."""
        now = now or time.time()
        self.pinned = [c for c in self.pinned if now - c.t < 600]
        return self.pinned[0] if self.pinned else None

    def candidates(self, now: float | None = None, n: int = 8) -> list[Comment]:
        """Up to n questions worth weighing: fan club members and gifters first, then the newest.
        In a quiet chat the same viewer can get answered again much sooner: she answers as much as she can."""
        now = now or time.time()
        self._fresh(now)
        quiet = 0.1 + 0.9 * self.busyness(now)
        seen, out = set(), []
        for c in reversed(self.questions):  # newest first: she answers what's being asked now
            key = _norm(c.text)
            if key in seen or key in self.answered_texts:
                continue
            wait = (self.per_user if c.boost < 2 else self.per_user * 0.4) * quiet  # supporters: sooner
            if now - self.answered_users.get(c.user.lower(), -1e9) < wait:
                continue
            seen.add(key)
            out.append(c)
        out.sort(key=lambda c: c.boost - (now - c.t) / 90, reverse=True)  # a supporter's question stays on top longer
        return out[:n]

    def vip_waiting(self, since: float) -> bool:
        """A fan club member or gifter asked something since `since`: she shouldn't make them wait long."""
        return any(c.boost >= 2 and c.t > since for c in self.questions)

    def yams_ask(self, now: float | None = None, cooldown: float = 150.0) -> Comment | None:
        """Someone asked for her yams, and it's a good moment to shut it down again. Each time she does, the next one
        waits longer (2.5, 4, 6, then 9 min), and sometimes she just lets the flood go by: it's funnier rare."""
        now = now or time.time()
        self._fresh(now)
        wait = cooldown * (1.6 ** min(self.yams_answers, 3))
        if not self.yams or now - self.last_yams < wait:
            return None
        if random.random() < (0.25 if self.yams_answers else 0.0):  # ignored on purpose; ask again later
            self.last_yams = now - wait + 45
            self.yams = []
            return None
        return random.choice(self.yams)

    def yams_count(self, now: float | None = None) -> int:
        """How many yams asks are in chat right now (a flood gets a different reaction)."""
        now = now or time.time()
        return len({c.user for c in self.yams if now - c.t < 60})

    def skip(self, c: Comment):
        """Looked at and passed on: never weighed again (but the viewer can still get an answer to something else)."""
        self.answered_texts.add(_norm(c.text))
        self.questions = [q for q in self.questions if q.id != c.id]
        self.pinned = [q for q in self.pinned if q.id != c.id]

    def done(self, c: Comment, now: float | None = None, reply: str = ""):
        now = now or time.time()
        self.answered_users[c.user.lower()] = now
        self.answered_texts.add(_norm(c.text))
        self.questions = [q for q in self.questions if q.id != c.id]
        self.pinned = [q for q in self.pinned if q.id != c.id and _norm(q.text) != _norm(c.text)]
        yams = bool(YAMS.search(c.text))
        if yams:
            self.last_yams = now
            self.yams_answers += 1
            self.yams = []
        try:
            DATA.mkdir(exist_ok=True)
            with ANSWERED.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": c.id, "t": now, "q": c.text, "who": c.who, "reply": reply, "yams": yams,
                                    "pinned": c.pinned},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass


LORE = DATA / "stream_lore.md"  # running jokes and facts about the stream she knows; edit it any time
LORE_START = """# What Capri knows about the stream (one per line; edit freely, she rereads it every answer)
- Chat is OBSESSED with your "yams" and begs to see them every stream. It's the stream's running joke. You never give in.
- The streamer is Hibura, TikTok @hiburavt. You live on Hibura's desktop and go live with them.
- Your followers goal for "maybe thinking about" the yams: way more than now, like 10K. Never promise anything.
"""


def lore() -> list[str]:
    """The stream's running jokes and facts, from data/stream_lore.md (created with the yams one the first time)."""
    try:
        if not LORE.exists():
            DATA.mkdir(exist_ok=True)
            LORE.write_text(LORE_START, encoding="utf-8")
        return [ln.strip()[2:].strip() for ln in LORE.read_text(encoding="utf-8").splitlines()
                if ln.strip().startswith("- ") and len(ln.strip()) > 3]
    except OSError:
        return []


def followers() -> int | None:
    """@hiburavt's follower count, as the chat app last saw it (None if it's older than an hour or unknown)."""
    try:
        d = json.loads((DATA / "live.json").read_text(encoding="utf-8"))
        if d.get("followers") is not None and time.time() - float(d.get("followers_at", 0)) < 3600:
            return int(d["followers"])
    except (OSError, ValueError, TypeError):
        pass
    return None


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", (text or "").lower()))


class Tail:
    """Reads new comments the chat app appended to live_chat.jsonl since last time (survives the file being reset)."""

    def __init__(self, path=CHAT, from_start: bool = False):
        self.path = path
        self.pos = 0 if from_start else (path.stat().st_size if path.exists() else 0)

    def read(self) -> list[Comment]:
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self.pos:
            self.pos = 0  # new session: the app started a fresh file
        if size == self.pos:
            return []
        with self.path.open("rb") as f:
            f.seek(self.pos)
            data = f.read()
        cut = data.rfind(b"\n") + 1  # leave a half-written last line for next time
        self.pos += cut
        out = []
        for line in data[:cut].decode("utf-8", "ignore").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind", "comment") == "comment":
                out.append(Comment(str(d.get("id", "")), d.get("nick", ""), d.get("user", ""), d.get("text", ""),
                                   float(d.get("t", time.time())), int(d.get("club") or 0), int(d.get("gifts") or 0),
                                   bool(d.get("top")), bool(d.get("pinned"))))
        return out


def add_idea(text: str, who: str = "") -> None:
    """One line onto the ideas board (data/ideas.md), under "From chat" for viewers' ideas."""
    DATA.mkdir(exist_ok=True)
    board = IDEAS.read_text(encoding="utf-8") if IDEAS.exists() else ""
    line = f"- {text.strip()}" + (f"  (from {who})" if who else "")
    head = "## From chat" if who else "## Ideas"
    if head not in board:
        board = board.rstrip() + f"\n\n{head}\n"
    i = board.index(head) + len(head)
    j = board.find("\n## ", i)
    j = len(board) if j < 0 else j
    section = board[i:j].rstrip()
    board = board[:i] + section + "\n" + line + "\n" + ("\n" + board[j:].lstrip("\n") if j < len(board) else "")
    IDEAS.write_text(board.lstrip("\n"), encoding="utf-8")

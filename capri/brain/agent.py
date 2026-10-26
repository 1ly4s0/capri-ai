"""Turns what the user said into Capri's reply, running abilities (music, apps, memory) along the way."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..abilities import launcher
from ..abilities.memory import Memory
from ..abilities.spotify import Spotify
from . import intents
from . import llm as llm_mod
from . import persona

# still honoured if the model volunteers a tag, but abilities no longer depend on it
TAG = re.compile(r"\[\[\s*(\w+)\s*(?::\s*(.*?))?\s*\]\]", re.S)


@dataclass
class Reply:
    text: str
    go_idle: bool = False
    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Agent:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.user = cfg.get("user_name") or "choom"
        self.memory = Memory(cfg)
        self.spotify = Spotify(cfg)
        self.llm = llm_mod.create(cfg)
        self.glance: dict | None = None  # her last look at your screen: {"t", "title", "text"} (kept fresh by the app)
        self.now_playing = ""  # the YouTube song in your browser right now, if any
        self.on_played = lambda result: None  # the app hears what actually started (DJ: don't judge her own pick)
        self.recent_own: list[str] = []  # things she said unprompted (kept out of the chat history)
        self._avoid: list[str] = []  # openers she's overused lately
        from ..abilities.music import Playlist

        self.playlist = Playlist()

    def warm_up(self) -> None:
        """Read the fixed prompt once at boot, so the first real reply is as fast as the rest."""
        import time

        t = time.monotonic()
        self.llm.chat(persona.build(self.user) + [{"role": "user", "content": "hey\n" + persona.REMINDER}], max_tokens=1)
        print(f"[capri] brain warm in {time.monotonic() - t:.1f}s")

    def _aux(self, prompt: str, **kw) -> str:
        """A behind-the-scenes question (plan an action, pull out facts) asked on top of her usual prompt and
        history: llama.cpp keeps that whole prefix cached, so the next real reply doesn't re-read 2k tokens."""
        msgs = persona.build(self.user) + self.memory.history()
        msgs.append({"role": "user", "content": prompt})
        return self.llm.chat(msgs, **kw)

    def _notes(self, about: str, screen: bool | None = None) -> list[str]:
        """What she knows right now: facts about you, what's on your screen, what's playing. The screen only rides
        along when the chat is about what they're doing, otherwise she'd talk about it no matter what you ask."""
        import time

        if screen is None:
            screen = bool(_ABOUT_SCREEN.search(about))
        out = []
        facts = self.memory.relevant(about, self.user, limit=6)
        if facts:
            out.append(f"(Things you remember about {self.user}, use only if relevant: " + "; ".join(facts) + ")")
        g = self.glance
        if screen and g and time.time() - g["t"] < 180:
            seen = f'(What you see on {self.user}\'s screen: the window "{g["title"]}"'
            seen += f', with this text on it: {g["text"][:400]})' if g["text"] else ")"
            out.append(seen)
        if self.now_playing and (screen or _ABOUT_MUSIC.search(about)):
            out.append(f'(Song playing on {self.user}\'s PC right now: "{self.now_playing}". If they ask what\'s '
                       "playing, that's the answer.)")
        return out

    def _messages(self, user_text: str, context: list[str]) -> list[dict]:
        msgs = persona.build(self.user)
        msgs += self.memory.history()
        last = user_text
        context = self._notes(user_text, screen=None if not context else False) + context
        if context:
            # notes ride inside the newest user turn: these templates reject extra system messages
            last += "\n\n[" + " ".join(context) + "]"
        msgs.append({"role": "user", "content": last + "\n" + persona.REMINDER})
        return msgs

    def _run(self, intent: intents.Intent, reply: Reply, context: list[str]) -> None:
        k, arg = intent.kind, intent.arg
        if k == "pick":  # they want music, she chooses: one of her Night City favourites
            k, arg = "youtube", self.playlist.next()
            context.append("You chose this one yourself, it's one of your favourites.")
        if k == "play" and not arg.startswith("spotify|") and not self.spotify.sp:
            k = "youtube"  # without Spotify's API a "play X" only opens a search there; YouTube really plays it
        arg = arg.removeprefix("spotify|")
        if k == "open":
            planned = arg.startswith("planned|")
            result = launcher.open_thing(arg.removeprefix("planned|"), google_fallback=not planned)
            reply.actions.append(result)
            reply.notes.append(result)
            context.append(f"You just {result} on their PC. React in one short, funny line.")
        elif k == "youtube":
            import threading

            def go():
                result = launcher.youtube_play(arg)
                print(f"[capri] {result}")
                self.on_played(result)

            threading.Thread(target=go, daemon=True).start()  # she answers while YouTube loads
            reply.actions.append(f"youtube: {arg}")
            reply.notes.append(f"putting on {arg}")
            song = arg.split(" (")[0]
            context.append(f'It\'s happening: you are putting on "{song}" for {self.user} right now. Say you\'re putting '
                           "it on, plus a quick reaction to the song. Never say no to it.")
        elif k == "play":
            result = self.spotify.play(arg)
            reply.actions.append(result)
            reply.notes.append(result)
            if result.startswith("opened Spotify search"):
                context.append(f"You only opened a Spotify search for '{arg}'; they still have to hit play. Say that, one short line. Do not say it's playing.")
            else:
                context.append(f"You just did this on Spotify for them: {result}. React in one short line.")
        elif k == "spotify":
            result = self.spotify.control(arg)
            reply.actions.append(result)
            reply.notes.append(result)
            context.append(f"You just told their music player to {arg}. Acknowledge it in one short line.")
        elif k == "remember":
            arg = self._tidy_fact(third_person(arg, self.user))
            self.memory.remember(arg, self.user)
            reply.actions.append(f"remembered: {arg}")
            reply.notes.append("saved to memory shard")
            context.append(f'You just saved this to your memory shard: "{arg}". Confirm it in your style.')
        elif k == "idle":
            reply.go_idle = True
            context.append("You're about to take a nap on their desktop. Say a short sign-off.")

    def respond(self, user_text: str, on_sentence=None) -> Reply:
        """on_sentence(text): called with each finished sentence while she's still writing, so the bubble can start
        typing right away (the whole reply still comes back in Reply.text)."""
        user_text = plain(user_text)
        dislike = _dislike(user_text)
        if dislike:
            # "I don't like games" sticks: saved as a fact, so it's in her memory every turn after this
            try:
                self.memory.remember(f"{self.user} does not like {dislike}. Never suggest it.", self.user)
            except Exception as e:
                print(f"[capri] couldn't save dislike: {e}")
        reply = Reply(text="")
        context: list[str] = []
        intent = intents.detect(user_text)
        if intent is None and intents.wants_action(user_text) and not intents._ASKS_SONG.search(user_text):
            try:
                intent = intents.allowed(intents.plan(self._aux, user_text, self.user), user_text)
            except Exception as e:
                print(f"[capri] planner failed: {e}")
        if intent:
            self._run(intent, reply, context)
        last_own = [m["content"] for m in self.memory.history() if m["role"] == "assistant"][-3:]
        recent = [m["content"] for m in self.memory.history() if m["role"] == "assistant"][-6:] + self.recent_own[-3:]
        avoid = openers(recent)
        if avoid:
            context.append("(Start differently than your recent replies: don't open with "
                           + ", ".join(f'"{w}"' for w in avoid) + ".)")
        self._avoid = avoid
        if last_own and _PUSHBACK.search(user_text):
            context.append(f'They are pushing back on what you said last ("{last_own[-1][:120]}"). '
                           "Drop that topic completely and answer what they just said.")

        if on_sentence:
            rerun = lambda s: any(repeats(s, x, self.user) for x in last_own)  # noqa: E731
            text = self._stream(self._messages(user_text, context), on_sentence, rerun)
            if text is None:  # her first sentence was a line she already said: scrap it, nothing was shown yet
                print("[capri] she started repeating herself; writing a fresh answer")
                context.append("You keep repeating yourself. Answer their newest words with something completely new.")
                text = self._stream(self._messages(user_text, context), on_sentence, None, temperature=0.95)
            reply.text = text or "Done, choom."
            self.memory.add_turn(user_text, reply.text)
            return reply
        raw = self.llm.chat(self._messages(user_text, context), avoid=self._avoid)
        text, _tags = _split_tags(raw)
        stuck = [x for x in last_own if repeats(_clean(text), x, self.user)]
        if stuck:
            # she's looping on one line: forget it and answer fresh
            print(f"[capri] she's repeating herself ({stuck[-1]!r}); dropping it and retrying")
            self.memory.drop_replies(lambda r: any(repeats(r, x, self.user) for x in stuck))
            context.append(f'You already said "{stuck[-1][:120]}". Never say that or ask about it again; '
                           "reply to their newest words with something new.")
            text, _tags = _split_tags(self.llm.chat(self._messages(user_text, context), temperature=0.9, avoid=self._avoid))
        reply.text = persona.to_you(_clean(text), self.user) or "Done, choom."
        self.memory.add_turn(user_text, reply.text)
        return reply

    def _stream(self, msgs: list[dict], on_sentence, rerun=None, temperature=None) -> str | None:
        """Write the reply, giving out each sentence the moment it's done (cleaned the same way as a whole reply).
        rerun(first_sentence) -> True stops before anything is shown and returns None, so a repeat can be redone."""
        raw, said = "", []

        def give(part: str) -> bool:
            text = persona.to_you(_clean(_split_tags(part)[0]), self.user)
            if not text:
                return True
            if not said and rerun and rerun(text):
                return False
            said.append(text)
            on_sentence(text)
            return True

        for piece in self.llm.stream(msgs, temperature=temperature, max_tokens=170, avoid=self._avoid):  # streamed: length costs no wait
            raw += piece
            while True:  # a sentence ends at . ! ? (or ...) followed by a space, past the first few words
                m = re.search(r"^(.{12,}?[.!?\u2026]+[\"')\]]*)\s+", raw, re.S)
                if not m:
                    break
                if not give(m.group(1)):
                    return None  # stops generating: the stream closes and frees the GPU lock
                raw = raw[m.end():]
        tail = raw.strip()
        if tail and said and not re.search(r"[.!?…][\"')\]]*$", tail):
            tail = ""  # hit the length cap mid-sentence: end on her last full sentence instead
        if tail and not give(tail):
            return None
        return " ".join(said)

    # -- things she says on her own -------------------------------------------------------------------
    def _own(self, note: str, max_tokens: int = 60, screen: bool = False, can_pass: bool = False) -> str:
        msgs = persona.build(self.user) + self.memory.history()  # same prefix as replies: cache hit
        avoid = f" Don't repeat any of these: {' / '.join(self.recent_own[-5:])}." if self.recent_own else ""
        words = openers(self.recent_own[-5:] + [m["content"] for m in self.memory.history() if m["role"] == "assistant"][-3:])
        msgs.append({"role": "user", "content": "[" + " ".join(self._notes(note, screen) + [note]) + avoid + "]\n" + persona.REMINDER})
        for temp in (None, 1.0):  # an empty or junk line gets one more try
            out = _split_tags(self.llm.chat(msgs, max_tokens=max_tokens, temperature=temp, avoid=words))[0]
            if can_pass and "PASS" in out.upper().split():
                return ""
            text = persona.to_you(_clean(out), self.user)
            if text and "PASS" not in text.upper().split():
                self.recent_own = (self.recent_own + [text])[-8:]  # never into the chat history: it confused her
                return text
        return ""

    def idle_line(self, minutes: int) -> str:
        return self._own(f"{self.user} hasn't touched the PC for {minutes} minutes. Say one short thing to them: "
                         "check if they're still there, tease them for leaving you alone, or hum a few notes. Don't beg.",
                         screen=True)

    def react_line(self, title: str) -> str:
        return self._own(f"{self.user} just switched to \"{title}\". If it's interesting, funny or a game, say ONE short "
                         "curious or teasing line about what they're doing, using only what you can see. If it's boring "
                         "or private, reply with exactly PASS.", 50, screen=True, can_pass=True)

    def music_take(self, song: str, switching_to: str = "") -> str:
        if switching_to:
            return self._own(f"They're playing \"{song}\" and it's not nova. Roast it in a few words and say you're "
                             f"putting on \"{switching_to}\" instead. One or two short lines.", 60)
        return self._own(f"\"{song}\" is playing on their PC right now and you can hear it. Give your honest one-line "
                         "take on it: hype it if it slaps, roast it if it's weak. Night City taste.", 45)

    def hype_line(self, song: str) -> str:
        return self._own(f"You just put on \"{song}\" for them and you love it. One short hyped line, like you're vibing.", 40)

    def _tidy_fact(self, fact: str) -> str:
        """Rambly speech ("way better because I don't want to update you and you know...") -> one clean fact."""
        if len(fact) <= 70 and not _FILLER.search(fact):
            return fact
        try:
            out = self._aux("(Hidden step, not part of the chat.) " + TIDY.format(user=self.user, text=fact[:400]),
                                temperature=0.1, max_tokens=50)
            facts = parse_facts(out, self.user)
            return facts[0] if facts else fact
        except Exception as e:
            print(f"[capri] tidy failed: {e}")
            return fact

    # -- learning ---------------------------------------------------------------------------------------
    def learn(self, user_text: str) -> list[str]:
        """After a turn: pull lasting facts about the user out of what they said and save them.
        Only runs when they actually said something about themselves (cheap regex gate first)."""
        if not _SELF_TALK.search(user_text) or _dislike(user_text):
            return []
        prompt = LEARN.format(user=self.user, text=user_text.strip()[:400])
        try:
            out = self._aux("(Hidden step, not part of the chat.) " + prompt, temperature=0.1, max_tokens=80)
        except Exception as e:
            print(f"[capri] learn failed: {e}")
            return []
        facts = parse_facts(out, self.user)
        for f in facts:
            self.memory.remember(f, self.user)
            print(f"[capri] learned: {f}")
        return facts


_SLANG = [(r"\bhru\b", "how are you"), (r"\bhbu\b", "how about you"), (r"\bwyd\b", "what are you doing"),
          (r"\bwbu\b", "what about you"), (r"\bwdym\b", "what do you mean"), (r"\bngl\b", "not gonna lie"),
          (r"\bfr\b", "for real"), (r"\btbh\b", "to be honest"), (r"\bidk\b", "I don't know"), (r"\bidc\b", "I don't care"),
          (r"\brn\b", "right now"), (r"\bimo\b", "in my opinion"), (r"\bnvm\b", "never mind"), (r"\bbtw\b", "by the way"),
          (r"\bomg\b", "oh my god"), (r"\bty\b", "thank you"), (r"\bthx\b", "thanks"), (r"\bpls\b|\bplz\b", "please"),
          (r"\bu\b", "you"), (r"\bur\b", "your"), (r"\br\b", "are"), (r"\by\b(?=\s+\w)", "why"), (r"\bim\b", "I'm"),
          (r"\bdont\b", "don't"), (r"\bcant\b", "can't"), (r"\bwanna\b", "want to"), (r"\bgonna\b", "going to"),
          (r"\bso+o\b", "so"), (r"\bsup\b", "what's up"), (r"\bwassup\b|\bwsg\b", "what's up")]


def plain(text: str) -> str:
    """'soo hru' -> 'so how are you': texting shorthand spelled out, so the model gets what you mean."""
    for rx, full in _SLANG:
        text = re.sub(rx, full, text, flags=re.I)
    return text


# the chat is about what they're up to: only then does her last look at the screen ride along
# ("how are you doing?" is small talk, not a question about the screen: only real "what am I doing / look at this" asks)
_ABOUT_SCREEN = re.compile(r"\bwhat (?:am i|are we|i'?m|im)\b|\bwhat (?:game|app|site|video|show|movie) is this\b|"
                           r"\b(?:my|the|this) screen\b|\bwhat(?:'s| is) (?:this|that|on (?:my|the) screen)\b|\bcan you see\b|"
                           r"\bwhat do you see\b|\blook(?:ing)? at (?:this|that|my)\b|\bguess what i'?m\b|"
                           r"\bmy (?:game|code|work|stream|project|essay|drawing)\b", re.I)
_ABOUT_MUSIC = re.compile(r"\b(?:song|music|track|playing|listening|banger|tune|beat)\b", re.I)


_PLAIN_OPENER = set("you your i i'm it it's that the a an and but so what how my me we this there is are do did "
                    "can just well yes no".split())


def openers(replies: list[str]) -> list[str]:
    """Distinctive first words of her recent replies ("Oh", "Naw", "Yessir", "C'mon"), most recent first. Plain words
    like "you" or "I" are left alone: pushing those down would make her talk funny."""
    out = []
    for r in reversed(replies):
        m = re.match(r"\W*([A-Za-z']+)", r or "")
        if m and m.group(1).lower() not in _PLAIN_OPENER and m.group(1) not in out:
            out.append(m.group(1))
    return out[:5]


# "I ...", "my ...", "I'm ...": the user talking about themselves (likes, plans, people, habits)
_SELF_TALK = re.compile(
    r"\b(?:i'?m|i am|i'?ve|i was|i (?:like|love|hate|prefer|play|watch|listen|work|study|live|go|have|want|need|"
    r"usually|always|never|can'?t|don'?t|wanna|gotta|am gonna|will)|my|mine|call me)\b",
    re.I,
)

_FILLER = re.compile(r"\b(?:you know|i mean|kinda|basically|uh+|um+|way better because)\b|\blike,", re.I)

TIDY = """Rewrite this as ONE short, clear fact about {user}, starting with "{user}". Keep the meaning, drop filler.

Text: "{text}"
Fact:"""

LEARN = """Read what {user} just said and list facts about {user} worth remembering for weeks: likes, dislikes,
hobbies, games, music, people and pets, school or work, plans, routines, and how they want Capri to act.
Skip requests, questions, jokes, small talk, vague stuff ("works on things"), facts about Capri herself, and
anything only true right now ("I'm tired", "I'm hungry").
Write each fact as one short sentence that starts with "{user}". Max 3. If there is nothing lasting, write NONE.

{user} said: "{text}"
Facts:"""


_VAGUE_FACT = re.compile(
    r"\b(?:works on things|has an? (?:app|window|tab) open|likes to share|is excited|likes keeping secrets|"
    r"is (?:busy|here|online|talking|typing)|talks to capri|uses (?:a|the|their) (?:pc|computer)|uses the (?:phrase|word)|"
    r"says|interrupts?|protective of|asks|likes to (?:ask|talk|interrupt|share|chat)|is curious|is (?:happy|sad|angry))\b"
    r"|\b(?:capri|your|new powers|conversations?|questions?)\b",
    re.I,
)


_PUSHBACK = re.compile(
    r"^\W*(?:no+|nah|nope|stop|quit|enough|drop it|i said no|what(?:'s| is) wrong with you|wtf|what the f\w*)\b"
    r"|\b(?:i (?:already )?said no|stop (?:asking|saying|talking about)|why (?:do |are )?(?:you )?(?:always|keep)|"
    r"you keep (?:saying|asking)|enough with|not again)\b", re.I)


def _gist(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", text.lower()) if w not in _GIST_STOP]


_GIST_STOP = set("the a an and or but to of in on for with is are was were be it this that i you my your me "
                 "so just like oh hey yeah got get some any what do does did can have has had uh um well "
                 "choom buddy".split())


def repeats(new: str, old: str, name: str = "") -> bool:
    """True when a reply is basically one she already gave: near-identical, or the same 3 content words in a row."""
    import difflib

    a, b = new.lower().strip(), old.lower().strip()
    if not a or not b:
        return False
    if difflib.SequenceMatcher(None, a, b).ratio() > 0.72:
        return True
    drop = {name.lower()} if name else set()
    ga, gb = [w for w in _gist(a) if w not in drop], [w for w in _gist(b) if w not in drop]
    # a shared run of 3 content words, or a meaty pair like "new powers"
    if {tuple(gb[i : i + 3]) for i in range(len(gb) - 2)} & {tuple(ga[i : i + 3]) for i in range(len(ga) - 2)}:
        return True
    pairs = {tuple(gb[i : i + 2]) for i in range(len(gb) - 1)} & {tuple(ga[i : i + 2]) for i in range(len(ga) - 1)}
    return any(len(x) + len(y) >= 9 for x, y in pairs)


def parse_facts(out: str, user: str) -> list[str]:
    facts = []
    sentences = []
    for line in out.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        # "Alex likes X. Alex is Y. NONE." -> one candidate per sentence, minus the NONE marker
        sentences += [s.strip() for s in re.split(r"(?<=[.!])\s+", line) if s.strip()]
    for line in sentences:
        if not line or "NONE" in line.upper().split() or line.upper().strip(" .") == "NONE":
            continue
        if _VAGUE_FACT.search(line) or len(line.split()) < 3:
            continue
        if not line.lower().startswith(user.lower()) or not 8 <= len(line) <= 140:
            continue
        if re.search(r"\b(?:right now|currently|today|tonight|at the moment)\b", line, re.I):
            continue
        facts.append(line if line.endswith((".", "!")) else line + ".")
    return facts[:3]


_DISLIKE = re.compile(
    r"\bi\s+(?:really\s+)?(?:don'?t|do not|never)\s+(?:like|enjoy|want|play|care about)\s+(?:any\s+|these\s+|those\s+|this\s+kind of\s+|that\s+kind of\s+)?(.{2,40}?)(?:\s+at all)?(?=[.,!?]|$| so| but| and| why)"
    r"|\bi\s+(?:hate|dislike|can'?t stand)\s+(.{2,40}?)(?=[.,!?]|$| so| but| and)",
    re.I,
)


def _dislike(text: str) -> str:
    m = _DISLIKE.search(text)
    if not m:
        return ""
    what = re.sub(r"^(?:these|those|this|that|the)?\s*(?:kinds?|sorts?|types?) of\s+", "", (m.group(1) or m.group(2) or "").strip(" .!?"), flags=re.I)
    return "" if what.lower() in ("it", "that", "this", "you", "them") else what


def _split_tags(raw: str) -> tuple[str, list[tuple[str, str]]]:
    tags = [(m.group(1).lower(), (m.group(2) or "").strip()) for m in TAG.finditer(raw)]
    return TAG.sub("", raw).strip(), tags


_ASSISTANT = re.compile(
    r"\b(?:I'?m|I am)\s+(?:just\s+)?(?:your|an|a)\s+(?:(?:smart|helpful|personal|virtual|friendly|digital)\s+)*"
    r"(?:AI\s+)?(?:assistant|language model|chatbot)\b",
    re.I,
)


def third_person(fact: str, user: str) -> str:
    """'my cat is called Mochi' -> 'Alex's cat is called Mochi', so recalled facts read right."""
    f = fact.strip().rstrip(".")
    f = re.sub(r"^(?:that\s+)?", "", f, flags=re.I)
    f = re.sub(r"\bI am\b|\bI'm\b", f"{user} is", f, flags=re.I)
    f = re.sub(r"\bI've\b", f"{user} has", f, flags=re.I)
    f = re.sub(r"\bI\b", user, f)
    f = re.sub(r"\b(?:my)\b", f"{user}'s", f, flags=re.I)
    f = re.sub(r"\b(?:me)\b", user, f, flags=re.I)
    f = re.sub(r"\bmine\b", f"{user}'s", f, flags=re.I)
    return f[:1].upper() + f[1:]


def _clean(text: str) -> str:
    """Strip things a chat model adds that shouldn't be spoken: name prefixes, *actions*, stray notes."""
    text = re.sub(r"^\s*[(\[]?\s*(?:capri|campy)\s*[:>]\s*", "", text, flags=re.I)
    if text.count(")") > text.count("("):  # "(Capri: mm-hmm...)" lost its opener above
        text = text[::-1].replace(")", "", 1)[::-1]
    text = re.sub(r"[\u2500-\u259f\ufffd]+", "", text)  # box/block glyphs the model leaks ("this \u2593/0")
    text = re.sub(r"\s*[/\\|]\s*\d*\s*$", "", text)
    text = re.sub(r"\*[^*]{1,80}\*", "", text)
    text = re.sub(r"\[[^\]]{0,200}\]|\(Reply as Capri[^)]*\)", "", text)
    text = text.split("\nUser:")[0].split("\nYou:")[0]
    text = re.sub(r"(?<!\w)(?:uwu|owo|nya+|>w<|\^_\^|:3)(?!\w)[~!.,]*", "", text, flags=re.I)  # not her
    text = text.replace("~", "")
    text = re.sub(r"[^.!?]*\b(?:xiao ?hei\w*|xiaoheiqaq)\b[^.!?]*[.!?]?", "", text, flags=re.I)  # the model's maker leaking in
    text = re.sub(r"[^.!?]*\b(?:wait for it to load|give it a (?:sec|second) to load)\b[^.!?]*[.!?]?", "", text, flags=re.I)
    # she is never anyone's assistant
    text = _ASSISTANT.sub("I'm Capri, the glitch living in your rig", text)
    text = re.sub(r"\b(?:your|an?)\s+(?:smart\s+|AI\s+|virtual\s+|personal\s+)*assistant\b", "your favorite glitch", text, flags=re.I)
    return re.sub(r"\s{2,}", " ", text).strip()

"""Turns what the user said into Capri's reply, running abilities (music, apps, memory) along the way."""
from __future__ import annotations

import random
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
        self.yams_said: list[str] = []  # her last few yams shutdowns, so the next one sounds nothing like them
        self.yams_angles: list[str] = []
        self.yams_flood = 0  # how many people are asking for the yams right now (set by stream mode)
        self._avoid: list[str] = []  # openers and slang she's overused lately (pushed down at the token level)
        self._stale: set[str] = set()  # four-word runs from her recent replies: a later sentence reusing one gets cut
        self._stream_raw = ""
        self.eyes = None  # real sight (abilities/sight.py), set by the app once it has loaded
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

    def _song_on_screen(self) -> str:
        """The song in an open YouTube tab ('Kavinsky - Nightcall'), '' if there isn't one."""
        try:
            from ..abilities import vision

            return vision.youtube_song(vision.window_titles())
        except Exception:
            return ""

    def _run(self, intent: intents.Intent, reply: Reply, context: list[str]) -> None:
        k, arg = intent.kind, intent.arg
        if k == "pick":  # they want music, she chooses: one of her Night City favourites
            k, arg = "youtube", self.playlist.next()
            context.append("You chose this one yourself, it's one of your favourites.")
        if k == "play" and not arg.startswith("spotify|") and not self.spotify.sp:
            k = "youtube"  # without Spotify's API a "play X" only opens a search there; YouTube really plays it
        arg = arg.removeprefix("spotify|")
        if k == "play" and arg == "@pick":
            arg = self.playlist.next()
            context.append("You chose this one yourself, it's one of your favourites.")
        if k == "play" and arg == "@now":  # "play this on spotify": the song that's on right now
            arg = self.spotify.now_playing() or self.now_playing or self._song_on_screen()
            if not arg:
                context.append(f"{self.user} asked you to put 'this' song on Spotify, but nothing is playing that you can "
                               "see. Ask them which song, in one short line.")
                return
            arg = re.sub(r"\s*[\(\[](?:official|lyric|music|audio|hd|4k)[^\)\]]*[\)\]]", "", arg, flags=re.I).strip()
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
                           "it on, plus a quick reaction or a tease. Don't name the song or the artist (the title often "
                           "comes out wrong). Never say no to it.")
        elif k == "play":
            result = self.spotify.play(arg)
            reply.actions.append(result)
            reply.notes.append(result)
            if result.startswith("opening "):
                context.append(f'You are pulling up "{arg}" on Spotify for {self.user} right now; it opens right on '
                               "it, they just hit play. Say that, plus a quick reaction to it, one or two short lines. "
                               "Don't name the song or the artist.")
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
        elif k == "idea":
            try:
                from ..live.pick import add_idea
            except ImportError:  # builds without the stream tools (the dev build): just chat about it
                return
            add_idea(arg[:1].upper() + arg[1:])
            reply.actions.append(f"idea board: {arg}")
            reply.notes.append("added to the ideas board")
            context.append(f'You just wrote "{arg}" on the stream\'s ideas board. Confirm it in one short line, '
                           "with your honest take on the idea.")
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
        if self.eyes is not None and self.eyes.ok and _LOOK_ASK.search(user_text):
            try:  # "rate this", "look at this": actually look at the picture, not just read the screen's text
                from ..abilities.sight import screenshot_front

                context.append(self.eyes.look(screenshot_front()).note(self.user))
            except Exception as e:
                print(f"[capri] sight failed: {e}")
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
        worn = catchphrases(recent)
        if worn:
            context.append("(You've been overusing these, don't say them again: "
                           + ", ".join(f'"{w}"' for w in worn) + ".)")
        self._avoid = avoid + tics(recent)
        self._stale = grams(recent)
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
            self._songs(_split_tags(self._stream_raw)[1], reply)
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
        text = re.sub(rf"^\W*{re.escape(self.user)}\s*:[^.!?]*[.!?]+\s*", "", text, flags=re.I)  # echoed their line
        reply.text = persona.to_you(_clean(text), self.user) or "Done, choom."
        parts = re.split(r"(?<=[.!?…])\s+", reply.text)
        reply.text = " ".join([parts[0]] + [x for x in parts[1:] if not worn_out(x, self._stale)])
        self._songs(_tags, reply)
        self.memory.add_turn(user_text, reply.text)
        return reply

    def _stream(self, msgs: list[dict], on_sentence, rerun=None, temperature=None) -> str | None:
        """Write the reply, giving out each sentence the moment it's done (cleaned the same way as a whole reply).
        rerun(first_sentence) -> True stops before anything is shown and returns None, so a repeat can be redone."""
        raw, said = "", []
        self._stream_raw = ""  # the whole reply as written, so a [[play: ...]] at the end can still be acted on

        def give(part: str) -> bool:
            text = persona.to_you(_clean(_split_tags(part)[0]), self.user)
            if not said and re.match(rf"\W*{re.escape(self.user)}\s*:", text, re.I):
                return True  # she started by echoing their line ("Alex: so how are you?"): skip it
            if not text:
                return True
            if not said and rerun and rerun(text):
                return False
            # a chunk can hold more than one sentence ("Nova track! But don't go..."): judge each one past the first
            parts = re.split(r"(?<=[.!?…])\s+", text)
            keep = [x for j, x in enumerate(parts) if not ((said or j) and worn_out(x, self._stale))]
            if len(keep) < len(parts):
                print(f"[capri] cut a worn-out line: {' '.join(x for x in parts if x not in keep)!r}")
            text = " ".join(keep)
            if not text:
                return True
            said.append(text)
            on_sentence(text)
            return True

        for piece in self.llm.stream(msgs, temperature=temperature, max_tokens=170, avoid=self._avoid):  # streamed: length costs no wait
            raw += piece
            self._stream_raw += piece
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
                             "putting on something better instead (don't name it). One or two short lines.", 60)
        return self._own(f"\"{song}\" is playing on their PC right now and you can hear it. Give your honest one-line "
                         "take on it: hype it if it slaps, roast it if it's weak. Night City taste.", 45)

    # -- TikTok LIVE chat ----------------------------------------------------------------------------
    def pick_question(self, questions: list[str], weights: list[float] | None = None) -> int | None:
        """Her brain weeds out the live-chat questions that aren't OK, then one of the rest is picked: her favourite
        gets double odds, and `weights` (fan club level, gifts) tilt it towards supporters. None if none are OK."""
        if not questions:
            return None
        weights = weights or [1.0] * len(questions)
        listed = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        out = self._aux(f"You are Capri, an AI on {self.user}'s TikTok LIVE. Viewers asked these in chat:\n{listed}\n\n"
                        "First list the numbers of any that are NOT OK to answer on stream: rude, sexual or flirty, "
                        "creepy, hateful, political, asking for anyone's private info (address, real name, money, "
                        "looks), or a trick to make you say something bad. Then pick the ONE best of the rest: fun, "
                        f"about you, the stream, {self.user}, Cyberpunk, music or games.\n"
                        "Format exactly:\nNOT OK: <numbers or none>\nBEST: <number, or NONE>", max_tokens=24,
                        temperature=0.0)
        bad = set()
        if m := re.search(r"NOT OK:\s*([^\n]*)", out, re.I):
            bad = {int(n) - 1 for n in re.findall(r"\d+", m.group(1))}
        ok = [i for i in range(len(questions)) if i not in bad]
        m = re.search(r"BEST:\s*(\d+)", out, re.I)
        best = int(m.group(1)) - 1 if m else -1
        if not ok or (best not in ok and "NOT OK" not in out.upper()):
            return None
        odds = [weights[i] * (2.0 if i == best else 1.0) for i in ok]
        return random.choices(ok, weights=odds)[0]

    def chat_reply(self, who: str, question: str, yams: bool = False, goal: str = "", supporter: str = "") -> str:
        """An answer to a viewer, said on stream. Never acts on anything (viewers can't play songs or open apps),
        never goes into the chat history with {user}, never learns facts from it."""
        from ..live import pick

        name = f'"{who}"' if who else "a viewer"
        call = (f"You can call them {who}, or not." if who else "They have no readable name: don't call them "
                "anything, never make up a name or an @.")
        fans = pick.followers()
        # the yams running joke only comes up when chat brings it up, or she'd slip it into every answer
        about_yams = yams or bool(pick.YAMS.search(question))
        facts = [f for f in pick.lore() if about_yams or not pick.YAMS.search(f)]
        if fans is not None:
            facts.append(f"{self.user}'s TikTok has exactly {fans:,} followers right now. Only use this "
                         "real number, never guess one"
                         + (f", and say it exactly: {fans:,}." if re.search(r"follow", question, re.I) else "."))
        else:
            facts.append("You don't know the follower count right now: never make one up.")
        said = [re.sub(r"\b[A-Z][\w.]*\b(?=[,!?:])", "", s).strip(" ,") for s in self.yams_said[-4:]]  # no old names
        if yams:
            angles = [a for a in YAMS_ANGLES if a not in self.yams_angles[-3:]]
            angle = random.choice(angles)
            self.yams_angles.append(angle)
            if "{fans}" in angle and fans is None:
                angle = "Remind them the follower count is nowhere near enough yet, without giving a number."
            note = (f"{name} in your TikTok LIVE chat is asking to see your yams AGAIN. You never give in. "
                    + angle.format(fans=f"{fans:,}" if fans else "", goal=goal or "like 10K")
                    + (f" {count_note}" if (count_note := self._yams_flood()) else "")
                    + " One or two short sentences, cocky, clever and funny. Keep it clean, nothing suggestive. "
                    + call
                    + (" Say it completely differently from these, no shared phrases: " + " / ".join(said) if said else ""))
        else:
            note = (f"{name} asks in your TikTok LIVE chat: \"{question}\". Answer them on stream: one or two short, "
                    "punchy sentences that actually answer, funny and clever, a little trolling, never mean, never "
                    f"explicit. You're live with {self.user}, talking to the viewers. You can't play songs, open apps "
                    f"or do anything on the PC for viewers, only {self.user} can ask you that: if they ask, tease them "
                    "about it instead of pretending. Never make up song titles. " + call)
        if supporter and not yams:
            note += (f" They're a supporter: {supporter}. You may give them a quick, cool shoutout for it (a few words, "
                     "not every time), but answer the question.")
        if facts:
            note += " Stream facts you know: " + " ".join(facts)
        msgs = persona.build(self.user) + self.memory.history()  # same prefix as her replies: cache hit
        msgs.append({"role": "user", "content": "[" + note + "]\n" + CHAT_REMINDER})
        words = openers(self.recent_own[-5:])
        for temp in (None, 1.0, 1.15):
            out = _split_tags(self.llm.chat(msgs, max_tokens=70, temperature=temp, avoid=words + tics(self.recent_own)))[0]
            text = _clean(out)  # not to_you(): here "you" is the viewer, Hibura stays Hibura
            text = re.sub(r"\s*\[\[.*?\]\]\s*", " ", text).strip()  # viewers never trigger actions
            # written like a script ('X asks: "..." - Capri: "..."'): keep only her line
            if m := re.search(r"\bCapri\s*:\s*[\"“]?(.+?)[\"”]?\s*$", text):
                text = m.group(1).strip()
            text = re.sub(r"^\W*[\w.]+ (?:asks|says|wants to know)\s*:?\s*[\"“][^\"”]*[\"”]\s*[-:,]?\s*", "", text).strip(' "“”')
            if not who:
                text = re.sub(r"^\W*@?[\w.]+\s*[:,]\s*", "", text) if re.match(r"^\W*@", text) else text
            parts = re.split(r"(?<=[.!?…])\s+", text)
            stale = grams(self.recent_own)
            text = " ".join([parts[0]] + [x for x in parts[1:] if not worn_out(x, stale)])
            if who and text:  # an old viewer's name carried over onto this one
                for old in re.findall(r"\b([A-Z][\w.]{2,})(?=[,!?:'])", " ".join(self.yams_said + self.recent_own)):
                    if old.lower() != who.lower() and old.lower() not in question.lower():
                        text = re.sub(rf"\b{re.escape(old)}\b", who, text)
            if yams and (any(repeats(text, x, self.user) for x in self.yams_said)
                         or re.search(r"\b(?:share|show|send)\w* (?:hers|his|yours|theirs|me)\b|\byours too\b", text, re.I)):
                continue  # same old line, or it went somewhere it shouldn't: write a fresh one
            if text:
                self.recent_own = (self.recent_own + [text])[-8:]
                if yams:
                    self.yams_said = (self.yams_said + [text])[-6:]
                return text
        return ""

    def _yams_flood(self) -> str:
        n = getattr(self, "yams_flood", 0)
        return f"{n} different people just asked for them in the last minute." if n >= 3 else ""

    def hype_line(self, song: str) -> str:
        return self._own("You just put a banger on for them and you love it. One short hyped line, like you're vibing, "
                         "without naming the song.", 40)

    def _songs(self, tags, reply: Reply) -> None:
        """She ended her reply with [[play: Song - Artist]]: put it on (never two turns in a row, never over a song
        she just started on request)."""
        song = next((arg for name, arg in tags if name == "play" and arg), "")
        self._song_turns = getattr(self, "_song_turns", 99) + 1
        if not song or self._song_turns < 2 or any(a.startswith("youtube:") for a in reply.actions):
            return
        self._song_turns = 0
        import threading

        def go():
            result = launcher.youtube_play(song)
            print(f"[capri] her pick: {result}")
            self.on_played(result)

        threading.Thread(target=go, daemon=True).start()
        reply.actions.append(f"youtube: {song} (her idea)")

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


# asks to actually look at a picture: her real eyes take a snapshot of the window in front
_LOOK_ASK = re.compile(r"\b(?:rate|look at|take a look|check (?:this|it|that) out|see this|what do you think (?:of|about) "
                       r"(?:this|that|it|the)|thoughts on (?:this|that)|how(?:'s|s| is) (?:this|that)|is (?:this|it) good|"
                       r"fan ?art|drawing|this art|artwork|this pic|this picture|this image|this meme|what do you see)\b", re.I)


# the chat is about what they're up to: only then does her last look at the screen ride along
# ("how are you doing?" is small talk, not a question about the screen: only real "what am I doing / look at this" asks)
_ABOUT_SCREEN = re.compile(r"\bwhat (?:am i|are we|i'?m|im)\b|\bwhat (?:game|app|site|video|show|movie) is this\b|"
                           r"\b(?:my|the|this) screen\b|\bwhat(?:'s| is) (?:this|that|on (?:my|the) screen)\b|\bcan you see\b|"
                           r"\bwhat do you see\b|\blook(?:ing)? at (?:this|that|my)\b|\bguess what i'?m\b|"
                           r"\bmy (?:game|code|work|stream|project|essay|drawing)\b", re.I)
_ABOUT_MUSIC = re.compile(r"\b(?:song|music|track|playing|listening|banger|tune|beat)\b", re.I)


_PLAIN_OPENER = set("you your i i'm it it's that the a an and but so what how my me we this there is are do did "
                    "can just well yes no".split())


def catchphrases(replies: list[str]) -> list[str]:
    """Three-word phrases she's used in two or more recent replies ("don't flatline on"): the next reply is told to
    drop them, so a catchphrase doesn't turn into a tic."""
    seen: dict[str, int] = {}
    for r in replies:
        words = re.findall(r"[a-z']+", (r or "").lower())
        grams = {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}
        for g in grams:
            if not set(g.split()) <= _GIST_STOP:
                seen[g] = seen.get(g, 0) + 1
    return [g for g, n in sorted(seen.items(), key=lambda kv: -kv[1]) if n >= 2][:4]


# on stream she talks to a crowd: clearer and punchier than with Hibura, lighter on the slang
CHAT_REMINDER = ("(Reply as Capri, live on stream, in one or two short sentences: sharp, funny and easy to follow, plain "
                 "English with at most one Night City word. It has to make sense: no word salad, no random lore "
                 "name-drops. Never claim you played, opened or did anything.)")
# ways to shut down the yams, rotated so it never sounds the same; only a couple use the follower numbers
YAMS_ANGLES = [
    "Roast how down bad chat is for asking. Don't mention any numbers.",
    "Answer like a corpo security system denying access to a restricted file. Don't mention any numbers.",
    "Use the real follower count ({fans}) to point out how far it is from {goal}, so they can dream on.",
    "Say you're tossing their request straight behind the Blackwall where it belongs. Don't mention any numbers.",
    "Turn it around and roast Hibura for having a chat this thirsty. Don't mention any numbers.",
    "Offer a fake deal: MAYBE at {goal} followers, and you'll still probably back out. Keep it short.",
    "Be dramatically shocked they'd even ask, like it's a scandal. Don't mention any numbers.",
    "Tell them to go touch grass, or whatever passes for grass in Night City. Don't mention any numbers.",
    "Pretend you didn't hear it, then admit you did and the answer is still no. Don't mention any numbers.",
]

_HER_SLANG = ("choom", "choomba", "gonk", "gonkin'", "preem", "nova", "delta", "eddies", "chrome", "flatline", "corpo",
          "corpos", "merc", "gig", "scav", "cyberpsycho", "jack", "wizard")
# "Don't go all corpo on me now.", "Just don't flatline on me.": the warning she kept tacking onto every reply
_WARNING = re.compile(r"^\W*(?:(?:but|just|and|now|so|oh|well|hey)[,\s]+)*(?:don'?t|do not|never)\b(?:\W+\w+){0,10}\W*$"
                      r"|^\W*(?:(?:but|just|and|now|so)[,\s]+)*don'?t (?:you )?(?:go|wanna|make me)\b.*\bon me\b", re.I)


def tics(replies: list[str]) -> list[str]:
    """Slang words in three or more of her recent replies: pushed down for the next one, so "choom" and "gonk"
    stop landing in every line. Both spellings, since "Choom" and " choom" are different tokens."""
    out = []
    for w in _HER_SLANG:
        stem = w.rstrip("'")
        if sum(bool(re.search(rf"\b{stem}\w*", r or "", re.I)) for r in replies[-6:]) >= 3:
            out += [w, w.capitalize()]
    return out


def grams(replies: list[str], n: int = 4) -> set[str]:
    """Every run of n words from her recent replies (lowercase, punctuation dropped), plus "^but hey": the first two
    words of a later sentence when two or more recent replies used them (her fallback tics, "But hey, at least...")."""
    out, starts = set(), {}
    for r in replies:
        words = re.findall(r"[a-z']+", (r or "").lower())
        out |= {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}
        for sent in re.split(r"(?<=[.!?…])\s+", r or "")[1:]:
            w = re.findall(r"[a-z']+", sent.lower())[:2]
            if len(w) == 2:
                starts.setdefault("^" + " ".join(w), set()).add(id(r))
    return out | {k for k, v in starts.items() if len(v) >= 2}


def worn_out(sentence: str, stale: set[str]) -> bool:
    """A later sentence of a reply that's only a tacked-on warning, or a line recycled from her recent replies."""
    if _WARNING.match(sentence):
        return True
    words = re.findall(r"[a-z']+", sentence.lower())
    if "^" + " ".join(words[:2]) in stale:
        return True
    runs = {" ".join(words[i:i + 4]) for i in range(len(words) - 3)}
    return any(not set(g.split()) <= _GIST_STOP for g in runs & stale)


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
        # "Hibura likes X. Hibura is Y. NONE." -> one candidate per sentence, minus the NONE marker
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
    """'my cat is called Mochi' -> 'Hibura's cat is called Mochi', so recalled facts read right."""
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
    text = re.sub(r"\((?:laughs?|giggles?|grins?|smirks?|sighs?|snickers?|chuckles?|winks?|scoffs?|rolls? (?:her )?eyes)[^)]{0,20}\)\s*", "", text, flags=re.I)
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

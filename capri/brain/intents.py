"""Spot ability requests in code: music (Spotify / YouTube), opening apps, remembering things, and goodbyes.
Clear-cut asks are caught by regex; vague ones that sound like an action go to a tiny planner call."""
from __future__ import annotations

import re
from dataclasses import dataclass

WAKE = r"^(?:(?:hey|yo|ok(?:ay)?|so)[,\s]+)?(?:capri|campy|capricorn)?[,\s]*"
POLITE = r"(?:(?:can|could|would|will) (?:you|u|ya)\s+|please\s+|pls\s+|go\s+(?:ahead\s+(?:and\s+)?)?|i want (?:you to\s+)?)*"


@dataclass
class Intent:
    kind: str  # play | youtube | pick (her choice of music) | spotify | open | remember | idea | idle
    arg: str = ""


_PLAY = re.compile(WAKE + POLITE + r"(?:play|put on|queue(?: up)?|blast|throw on)\s+(?:me\s+)?(.+?)(?P<sp>\s+on spotify)?[\s.!?]*$", re.I)
# anything aimed at Spotify: "play X in spotify", "put this on spotify", "spotify, play X", "open spotify and play X"
_SP_AT = r"\s+(?:on|in|with|from|using|through|thru|via|at)\s+(?:my\s+|the\s+)?spotify(?:\s+app)?"
_SPOTIFY = re.compile(
    WAKE + POLITE + r"(?:(?:open\s+(?:up\s+)?)?spotify[,\s]+(?:and\s+)?(?:play|put on|queue(?: up)?|blast|search(?: for)?|find)\s+(?:me\s+)?(?P<a>.+?)"
    r"|(?:play|put on|put|throw|queue(?: up)?|blast|throw on|search(?: for)?|find|look up|pull up|open)\s+(?:me\s+)?(?P<b>.+?)" + _SP_AT + r")"
    r"[\s.!?]*$", re.I)
# "this" in "play this on spotify": the song that's on right now
_THIS_SONG = re.compile(r"^(?:this|that|it|this (?:one|song|track|tune|banger)|that (?:one|song|track)|the (?:song|track)"
                        r"(?: (?:that'?s |that is |you'?re |thats )?playing)?|(?:the )?(?:current|same) (?:song|track|one)"
                        r"|what(?:'s| is|s)? playing(?: now| rn)?|whatever(?:'s| is) playing)$", re.I)
# "something like Ado", "songs by Ado", "I'm looking for something like, you know, like Ado": they named an artist
_HINT = re.compile(r"\b(?:(?:some(?:thing)?|some (?:music|songs?|tracks?|tunes?|stuff)|music|songs?|tracks?|tunes?|stuff|anything)"
                   r"\s+(?:(?:kinda|kind of|sort of)\s+)?(?:like|by|from|of)|(?:looking for|in the mood for|craving|vibing to)"
                   r"(?:\s+some(?:thing)?(?:\s+like)?)?)[,\s]+(?:(?:you know|y'?know|i mean|uh+|um+|like|maybe|idk)[,\s]+)*"
                   r"(?P<who>[^,.!?]+?)(?=\s*(?:[,.!?]|\s(?:on|in|with|from|using|through|via)\s+(?:my\s+|the\s+)?spotify\b|"
                   r"\s(?:for me|please|pls|plz|or something|or whatever|maybe|rn|right now|now|thanks|capri|choom)\b|$))", re.I)
_WANTS_MUSIC = re.compile(r"\b(?:play|put on|throw on|queue|blast|looking for|in the mood for|wanna hear|want to hear)\b", re.I)
_NOT_A_NAME = re.compile(r"^(?:music|something|anything|songs?|tracks?|stuff|that|this|it|good|chill|sad|happy|new|you|me|"
                         r"else|better|different|a (?:song|banger)|the (?:song|music))$", re.I)


def _hinted(t: str) -> str | None:
    """'...play some music in Spotify, I'm looking for something like Ado' -> 'Ado' (None if no artist is named)."""
    for m in _HINT.finditer(t):
        who = re.sub(r"^(?:(?:you know|like|the|some)[,\s]+)+", "", m.group("who").strip(), flags=re.I).strip(" '\"")
        if who and len(who.split()) <= 6 and not _NOT_A_NAME.match(who):
            return who
    return None


_YT = re.compile(WAKE + POLITE + r"(?:(?:play|watch|find|put on)\s+(.+?)\s+on youtube|(?:search\s+)?youtube(?:\s+for)?\s+(.+?))[\s.!?]*$", re.I)
_OPEN = re.compile(WAKE + POLITE + r"(?P<verb>open(?: up)?|launch|start(?: up)?|pull up|fire up|boot up|run)\s+(?:the\s+|my\s+)?(.+?)[\s.!?]*$", re.I)
_CTRL = [
    ("pause", re.compile(r"\b(pause|stop)\b.*\b(music|song|track|spotify|video|it|that)\b|^\W*(pause|stop the music)\W*$", re.I)),
    ("resume", re.compile(r"\b(resume|unpause|continue)\b.*\b(music|song|track|spotify|video|playing)\b|^\W*(resume|unpause)\W*$", re.I)),
    ("next", re.compile(r"\bskip\b|\bnext (?:song|track|one|video|tune|banger)\b|^\W*next\W*$", re.I)),
    ("previous", re.compile(r"\b(previous|last|go back)\b.*\b(song|track)\b", re.I)),
]
_BYE = re.compile(
    r"^\W*(?:(?:hey|ok(?:ay)?|alright)[,\s]+)?(?:capri|campy)?[,\s]*(?:(?:can|could) you\s+|you can\s+|just\s+)?"
    r"(?:go|leave|bye|bye bye|goodbye|good night|night|see ya|see you|cya|later|gotta go|i'?m out|peace)"
    r"(?:\s+(?:now|then|for now|capri|buddy|choom|later))*\W*$",
    re.I,
)
# "note this idea: ...", "add to the ideas board: ...", "idea for you: ...": onto the stream's ideas board
_IDEA = re.compile(r"\b(?:(?:note|write|put|save|add|jot)(?: down)? (?:this|that|an?|the|my|new)? ?idea|"
                   r"(?:add|put|write) (?:(?:this|that|it)\s+)?(?:to|on|in) (?:the |my |your )?ideas?(?: board| list| notepad)?|"
                   r"new idea|idea for (?:you|the board))\s*(?:for (?:you|the board))?[:,\s-]+(?:that\s+)?(.{4,})", re.I)
_REMEMBER = re.compile(r"\b(?:remember|don'?t forget|keep in mind|note)\s+(?:that\s+)?(.+)", re.I)
_IDLE = re.compile(r"\b(go (?:chill|to sleep|take a nap)|take a (?:break|nap)|be quiet|hush|leave me alone)\b", re.I)

# "play some music", "change the music", "put something better on": they want music, not a specific song
_PICK = re.compile(
    r"\b(?:change|switch|swap)\b.{0,20}\b(?:music|song|track|tune|it|this|that)\b"
    r"|\b(?:something|anything|a song|some(?:thing)?)\s+(?:else|better|different|good|nova|preem|cyberpunk|new)\b"
    r"|\b(?:play|put on|throw on|queue)\s+(?:me\s+|us\s+)?(?:some\s+|a\s+|any\s+)?(?:music|something|anything|songs?|tunes?|bangers?|tracks?|beats?)\b"
    r"|\b(?:your|ur)\s+(?:fav(?:ou?rite)?|pick|choice)\b.{0,15}\b(?:song|music|track)?",
    re.I,
)
_ASKS_SONG = re.compile(r"^\W*(?:yo\W+)?(?:capri\W+)?(?:whats|what(?:'s| is)?|which|who(?:'s| is)?|do you (?:like|know)|is this|name (?:of )?this)\b"
                        r".{0,25}\b(?:song|track|music|playing|this|artist|singing)\b[^.!]*\??\W*$", re.I)
# words people put after a request that are never part of a song title
_TAIL = re.compile(r"(?:[\s,]+(?:for me|for us|please|pls|plz|capri|campy|real quick|rn|right now|now|thanks|thank you|"
                   r"choom|buddy|bro|yo))+\s*$", re.I)

# vague asks: the planner decides ("change the song", "something else")
_VAGUE = re.compile(r"\b(?:this|that one|the one|something else|another one|different|change (?:it|this|that|the song)|"
                    r"boring|switch (?:it|this)|anything else|other one|instead)\b", re.I)


def detect(text: str) -> Intent | None:
    """Clear-cut asks only. Returns None for anything vague so plan() can think it through."""
    t = text.strip()
    if _BYE.match(t):
        return Intent("idle", "bye")
    if m := _IDEA.search(t):
        return Intent("idea", m.group(1).strip(" .!?\"'"))
    if m := _REMEMBER.search(t):
        return Intent("remember", m.group(1).strip(" .!?"))
    for action, rx in _CTRL:  # pause / skip / next first: "skip this song" is clear, not vague
        if rx.search(t) and re.search(r"\b(music|song|track|spotify|video|skip|next|pause|resume|unpause|previous)\b", t, re.I):
            return Intent("spotify", action)
    if _ASKS_SONG.search(t):
        return None  # answered from what's playing, nothing gets changed
    on_spotify = bool(re.search(r"\bspotify\b", t, re.I))
    if _WANTS_MUSIC.search(t) and (who := _hinted(t)):  # "play me something like Ado (on Spotify)"
        return Intent("play", ("spotify|" if on_spotify else "") + who)
    if m := _SPOTIFY.search(_TAIL.sub("", t.rstrip(" .!?,"))):
        what = _TAIL.sub("", m.group("a") or m.group("b")).strip(" .!?,\"'")
        what = re.sub(r"^some\s+(?=\S)(?!music$|songs?$|tunes?$)", "", what, flags=re.I)  # "play some Ado on spotify"
        if _THIS_SONG.match(what):
            return Intent("play", "spotify|@now")
        if what.lower() in ("", "music", "something", "some music", "a song", "anything", "some songs", "a banger",
                            "something good", "your favourite", "your favorite", "ur fav"):
            return Intent("play", "spotify|@pick")
        return Intent("play", "spotify|" + what)
    if _PICK.search(t) and not re.search(r"\b(?:called|named|by)\b", t, re.I):
        return Intent("play", "spotify|@pick") if on_spotify else Intent("pick")
    if _VAGUE.search(t) and not re.search(r"\b(?:spotify|on youtube)\b", t, re.I):
        return None
    if m := _YT.search(t):
        return Intent("youtube", _TAIL.sub("", (m.group(1) or m.group(2))).strip(" .!?,"))
    if m := _OPEN.search(t):
        what = m.group(2)
        if pm := re.search(r"\band (?:play|put on)\s+(.+)", what, re.I):
            return Intent("play", pm.group(1).strip(" .!?"))
        target = re.split(r"\s+(?:and|for me|please|real quick|rn|now)\b", what, maxsplit=1, flags=re.I)[0].strip(" .!?")
        loose_verb = m.group("verb").lower().split()[0] in ("start", "run", "boot", "fire")
        from ..abilities.launcher import APPS

        known = target.lower().removeprefix("the ").removesuffix(" app") in APPS
        # "start talking", "run away": only treat loose verbs as launches for apps we know
        if len(target.split()) <= 4 and (known or not loose_verb):
            return Intent("open", target)
    if m := _PLAY.search(t):
        what = _TAIL.sub("", m.group(1)).strip(" .!?,")
        what = re.sub(r"^(?:that|the) song (?:that )?(?:is |goes |that goes )?(?:like\s+)?", "", what, flags=re.I).strip(" ,")
        what = re.sub(r"^some\s+(?=\S)(?!music$|songs?$|tunes?$)", "", what, flags=re.I)  # "play some Ado"
        if what.lower() in ("", "music", "something", "some music", "a song", "anything"):
            return Intent("pick")
        if what.lower() not in ("it", "that"):
            return Intent("play", ("spotify|" if m.group("sp") else "") + what)
        return Intent("spotify", "resume")
    for action, rx in _CTRL:
        if rx.search(t) and re.search(r"\b(music|song|track|spotify|video|skip|next|pause|resume|unpause|previous)\b", t, re.I):
            return Intent("spotify", action)
    if _IDLE.search(t):
        return Intent("idle")
    return None


# -- planner: the "think before acting" step for vague asks -------------------------------------
PLANNER = """You are the brain of Capri, a desktop companion on {user}'s Windows PC. Decide what to DO about their
latest message.

{user} says: "{text}"

Actions:
PLAY <song or artist>          play a specific song or artist they named (or quoted lyrics from)
PICK                           they want music but didn't name a real song: you choose
SPOTIFY next|previous|pause|resume
OPEN <app or website>
NONE                           just talk, no action (the default: small talk, questions about you, feelings)
Only choose an action if THIS message asks for one, and only PLAY a real song or artist name.

Format exactly:
ACTION: <one action line>"""

_ACTION = re.compile(r"ACTION:\s*([A-Z_]+)\s*(.*)", re.I)
_FILLER_TARGET = re.compile(
    r"^(?:something|anything|some(?:thing)? else|another(?: one| song| track)?|a song|a different (?:one|song)|"
    r"music|some music|it|that|this|the (?:next|other) one|whatever|random)$",
    re.I,
)


def parse_plan(out: str) -> Intent | None:
    m = _ACTION.search(out) or re.search(r"^\s*([A-Z_]{3,})\s*(.*)$", out.strip(), re.M)
    if not m:
        return None
    verb, arg = m.group(1).upper(), m.group(2)
    arg = re.sub(r"\s*\(.*$|\s+\bif\b.*$|\s+on (?:spotify|youtube)\b.*$", "", arg, flags=re.I).strip().strip("<>\"' .")
    if verb == "PICK" or (verb == "PLAY" and arg and _FILLER_TARGET.match(arg)):
        return Intent("pick")
    if verb == "PLAY" and arg:
        return Intent("play", arg)
    if verb == "OPEN" and arg:
        return Intent("open", "planned|" + arg)  # planner guesses never turn into surprise Google searches
    if verb == "SPOTIFY" and arg.lower() in ("next", "previous", "pause", "resume"):
        return Intent("spotify", arg.lower())
    return None


_ACTIONISH = re.compile(
    r"\b(?:play|put on|turn on|queue|start|change|switch|skip|next|another|something else|different|youtube|spotify|"
    r"song|music|video|boring|open|launch)\b",
    re.I,
)
# what the user's own words must contain before a planner guess may DO something on the PC
_ASKS = {
    "music": re.compile(r"\b(?:play|put on|queue|throw on|blast|song|songs|music|track|spotify|youtube|skip|next|"
                        r"change (?:it|this|that|the song)|switch (?:it|this|songs?)|another|something else|boring|"
                        r"different (?:song|one|track)|pause|resume)\b", re.I),
    "open": re.compile(r"\b(?:open|launch|start|pull up|fire up|go to|bring up|load)\b", re.I),
}
_KIND_ASK = {"play": "music", "pick": "music", "spotify": "music", "youtube": "music", "open": "open"}
# "we're NOT listening to anything", "don't play that": the action word is there, but they're saying no to it
_NEGATED = re.compile(r"(?:\b(?:not|no|never|stop|quit)|n't)\s+(?:\w+\s+){0,2}?(?:play|playing|listen|listening|"
                      r"open|opening|music|songs?)\b", re.I)


_QUESTION_ONLY = re.compile(r"^\W*(?:what|which|who|when|where|how|why|are|were|is|do|did|does|have|wait)\b[^.!]*\??\W*$", re.I)
_ASK_TO_PLAY = re.compile(r"\b(?:can|could|would|will|why (?:don'?t|not)) you (?:play|put on|queue)\b|\b(?:play|put on) (?:me |us )?(?:some|a|the)\b", re.I)


def allowed(intent: Intent | None, text: str) -> Intent | None:
    """A planner guess only becomes an action if the user actually asked for that kind of thing."""
    if intent is None:
        return None
    if _NEGATED.search(re.sub(r"\b(?:why do|can|could|would|wo)(?:n'?t| not) you\b", "", text, flags=re.I)):
        return None
    need = _KIND_ASK.get(intent.kind)
    if need and not _ASKS[need].search(text):
        print(f"[capri] planner wanted {intent.kind} {intent.arg!r} but they didn't ask for it; just chatting")
        return None
    if intent.kind in ("play", "youtube", "pick") and _QUESTION_ONLY.match(text) and not _ASK_TO_PLAY.search(text):
        return None  # "what game do I play?" is a question, not a request
    if intent.kind in ("play", "youtube") and intent.arg.lower().strip(" ?!.") in text.lower().strip(" ?!."):
        if len(intent.arg.split()) >= len(text.split()) - 1:
            return None  # the planner echoed their whole sentence back as a "song"
    return intent


def wants_action(text: str) -> bool:
    """Small talk never reaches the planner, so it can't decide to do things on a whim."""
    return bool(_ACTIONISH.search(text))


def plan(ask, text: str, user: str) -> Intent | None:
    """ask(prompt, **kw) -> reply. The agent runs it on her cached prompt, so planning costs ~0.2 s, not a re-read."""
    out = ask(PLANNER.format(user=user, text=text) + "\n(This is a hidden system step: answer only with the ACTION line.)",
              temperature=0.0, max_tokens=16)
    print(f"[capri] plan: {out.strip()!r}")
    return parse_plan(out)

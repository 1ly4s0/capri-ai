"""Run with: python -m pytest tests  (no model or GPU needed)."""
from capri.brain import intents
from capri.brain.agent import _clean
from capri.brain.llm import _alternate
from capri.brain import persona


def kind(t):
    i = intents.detect(t)
    return (i.kind, i.arg) if i else None


def test_play():
    assert kind("Play Rebel Yell by Billy Idol on Spotify") == ("play", "spotify|Rebel Yell by Billy Idol")
    assert kind("hey capri, can you put on some synthwave") == ("play", "synthwave")
    assert kind("play some music") == ("pick", "")
    assert kind("play lofi on youtube") == ("youtube", "lofi")
    assert kind("youtube nightcall kavinsky") == ("youtube", "nightcall kavinsky")


def test_controls():
    assert kind("skip the song") == ("spotify", "next")
    assert kind("skip this song") == ("spotify", "next")  # clear control: no planner round trip
    assert kind("pause the music") == ("spotify", "pause")
    assert kind("next track") == ("spotify", "next")


def test_remember_idle():
    assert kind("Remember that my cat is called Mochi") == ("remember", "my cat is called Mochi")
    assert kind("go take a nap")[0] == "idle"
    assert kind("Capri, can you go?") == ("idle", "bye")
    assert kind("I love you, Campy.") is None




def test_alternate_and_persona():
    msgs = persona.build("Hibura") + [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "note"},
    ]
    out = _alternate(msgs)
    assert out[0]["role"] == "user" and "Hibura" in out[0]["content"]
    assert persona.build("Hibura") == persona.build("Hibura")  # fixed prefix: llama.cpp's cache depends on it
    assert all(a["role"] != b["role"] for a, b in zip(out, out[1:]))
    assert out[-1]["content"].endswith("note")


def test_clean():
    assert _clean("Capri: *smirks* Gonk. [note]") == "Gonk."


def test_identity_and_memory_wording():
    from capri.brain.agent import third_person

    assert "assistant" not in _clean("I'm your smart assistant. But you can call me Capri if you want.")
    assert third_person("my cat is called Mochi", "Hibura") == "Hibura's cat is called Mochi"
    assert third_person("I'm allergic to cats", "Hibura") == "Hibura is allergic to cats"


def test_open_and_browse():
    assert kind("Open Spotify") == ("open", "Spotify")
    assert kind("hey capri can you open discord for me") == ("open", "discord")
    assert kind("open spotify and play rebel yell") == ("play", "spotify|rebel yell")
    assert kind("play this in spotify pls") == ("play", "spotify|@now")
    assert kind("Capri, can you play this song on Spotify, please?") == ("play", "spotify|@now")
    assert kind("put that on spotify") == ("play", "spotify|@now")
    assert kind("play Symphony by Clean Bandit in spotify") == ("play", "spotify|Symphony by Clean Bandit")
    assert kind("spotify play never fade away") == ("play", "spotify|never fade away")
    assert kind("play some music on spotify") == ("play", "spotify|@pick")
    assert kind("play this") is None  # no Spotify: vague, the planner decides
    assert kind("start talking to me") is None
    p = intents.parse_plan
    assert p("ACTION: SPOTIFY next") == intents.Intent("spotify", "next")
    assert p("ACTION: NONE") is None
    assert p("ACTION: OPEN discord") == intents.Intent("open", "planned|discord")
    assert p("ACTION: PLAY bbno$ on Spotify (if not already playing)") == intents.Intent("play", "bbno$")
    assert p("ACTION: PLAY something else") == intents.Intent("pick")
    assert p("ACTION: PICK") == intents.Intent("pick")








def test_dislike():
    from capri.brain.agent import _dislike

    assert _dislike("I said I don't like these kind of games at all, why are you talking like I like them?") == "games"
    assert _dislike("i hate horror movies") == "horror movies"
    assert _dislike("I don't like it") == ""
    assert _dislike("I love you, Campy.") == ""


def test_to_you_rewrites_third_person_only():
    from capri.brain.persona import to_you

    assert to_you("Hibura doesn't want to update my code.", "Hibura") == "You don't want to update my code."
    assert to_you("Hibura does not like games. Never suggest it.", "Hibura") == "You do not like games. Never suggest it."
    assert to_you("Hibura's cat is called Mochi", "Hibura") == "Your cat is called Mochi"
    assert to_you("Hey Hibura, wanna play?", "Hibura") == "Hey Hibura, wanna play?"
    assert to_you("I made this for Hibura.", "Hibura") == "I made this for you."


def test_parse_facts():
    from capri.brain.agent import parse_facts

    out = "1. Hibura plays Valorant.\n- Hibura is tired right now\nCapri is cool\nNONE"
    assert parse_facts(out, "Hibura") == ["Hibura plays Valorant."]
    assert parse_facts("NONE", "Hibura") == []


def test_memory_relevant_and_dedupe(tmp_path):
    from capri.abilities.memory import Memory

    cfg = {"memory": {"file": str(tmp_path / "m.json"), "history_turns": 4}, "eru": {"memory": False}}
    m = Memory(cfg)
    m.remember("Hibura does not like games. Never suggest it.")
    for i in range(20):
        m.remember(f"Filler fact number {i} about stuff{i}.")
    m.remember("Hibura's cat is called Mochi.")
    m.remember("Hibura plays Valorant.")
    m.remember("Hibura plays Valorant a lot.")
    facts = m.relevant("how is my cat doing", "Hibura", limit=6)
    assert facts[0].startswith("Hibura does not like games")
    assert "Hibura's cat is called Mochi." in facts
    assert sum("Valorant" in f for f in m.facts()) == 1










def test_learner_drops_junk():
    from capri.brain.agent import parse_facts

    assert parse_facts("Hibura likes keeping secrets. Hibura is excited about their new powers. NONE.", "Hibura") == []
    assert parse_facts("Hibura works on things. Hibura has an app open often.", "Hibura") == []


def test_planner_guard():
    I = intents.Intent
    assert intents.allowed(I("play", "Hibura's favorite song"), "Hey, wait, are you sneaking a look at my code?") is None
    assert intents.allowed(I("play", "Rebel Yell"), "this is boring, play something by Billy Idol").kind == "play"
    assert intents.allowed(I("open", "planned|spotify"), "what is that on my screen?") is None
    assert intents.allowed(I("play", '"What game do I play?"'), "What game do I play?") is None
    assert intents.allowed(I("play", "lofi"), "can you play something chill, like lofi?").kind == "play"


def test_repeats_catches_her_loop():
    from capri.brain.agent import repeats

    a = "Uh... Hibura? You have new powers for me?"
    assert repeats("Hey, Hibura! You got some new powers for me?", a, "Hibura")
    assert repeats("What's new with you? You got some new powers for me to play with?", a, "Hibura")
    assert not repeats("Fine, fine. So what are you working on tonight?", a, "Hibura")
    assert not repeats("Hey Hibura, what's up?", "Hibura! You good?", "Hibura")


def test_pushback_and_negated_actions():
    from capri.brain.agent import _PUSHBACK
    from capri.brain.intents import Intent as I

    assert _PUSHBACK.search("No, I don't have any new power for you, Twin")
    assert _PUSHBACK.search("We're not listening to anything. Why always you're talking about listening to stuff?")
    assert not _PUSHBACK.search("Nothing much, just coding")
    assert intents.allowed(I("play", "x"), "We're not listening to anything. What is wrong with you?") is None
    assert intents.allowed(I("play", "Rebel Yell"), "don't play that") is None
    assert intents.allowed(I("play", "Rebel Yell"), "why don't you play Rebel Yell").kind == "play"


def test_clean_strips_afk_junk():
    assert _clean("(Capri: mm-hmm-hmm, da da da. Bored outta my skull)") == "mm-hmm-hmm, da da da. Bored outta my skull"
    assert _clean("Capri: hey") == "hey"
    assert _clean("Still there? this \u2593/0") == "Still there? this"


def test_voice_pronunciation():
    from capri.voice.tts import spoken

    assert spoken("Hey chooms, that's preem.") == "Hey chewms, that's preme."


def test_video_script_parses():
    from capri.config import ROOT
    from capri.desk.video import parse

    steps = parse(ROOT / "video.txt")
    assert ("drop", "") in steps and ("defrag", "") in steps
    assert ("say", "Hey chooms, how y'all doing?") in steps
    assert ("cmd", "") in steps


def test_hotkeys_and_youtube_titles():
    from capri.abilities.vision import youtube_song
    from capri.voice import hotkey

    assert hotkey.parse("ctrl+1") == [0x11, 0x31]
    assert hotkey.parse("Ctrl + Space") == [0x11, 0x20]
    assert hotkey.name({0x11, 0x41}) == "ctrl+a"
    assert youtube_song(["Claude", "(3) Kavinsky - Nightcall (Official Video) - YouTube - Brave"]) == "Kavinsky - Nightcall"
    assert youtube_song(["YouTube - Brave"]) == ""


def test_whisper_hallucination_filter():
    from capri.voice.stt import hallucination

    hot = "Capri, Campy, Capricorn, choom"
    assert hallucination("Capri, Capri, Capri, Capri, Capri, Capri", 3, hot)
    assert hallucination("Thanks for watching!", 1.0, hot)
    assert not hallucination("hey Capri what song is this", 2, hot)


def test_real_phrases_from_the_log():
    # what was actually said to her, and what went wrong before
    assert kind("Can you play some music for me, Capri, please?") == ("pick", "")  # was: played "Please Please Please"
    assert kind("Yo, just change the music for me please") == ("pick", "")  # was: a made-up "Bank Account"
    assert kind("play rebel yell for me capri") == ("play", "rebel yell")
    assert kind("Yo Capri, can you play that song that is like I just wanna be part of your symphony?") == (
        "play", "I just wanna be part of your symphony")
    assert kind("soo hru") is None
    assert kind("change the wallpaper") is None


def test_no_signature_endings():
    from capri.brain import agent as A

    recent = ["Nah nah nah, don't go all corpo on me now. Just spit it out, choom.",
              "Putting on Never Fade Away, choom. Don't go cryin' in your keyboard now.",
              "You tryna climb Arasaka Tower now? Take baby steps, choom."]
    assert A.worn_out("Don't go all corpo on me now.", set())
    assert A.worn_out("Just don't flatline on me, choom.", set())
    assert not A.worn_out("Corpos can choke on their eddies.", set())
    assert A.worn_out("Just spit it out, choom, I'm waiting.", A.grams(recent))  # recycled four-word run
    assert not A.worn_out("Show me the clip first.", A.grams(recent))
    assert "choom" in A.tics(recent) and "Choom" in A.tics(recent)
    assert "gonk" not in A.tics(recent)
    assert A.worn_out("Don't go Lucy on me now, can't have you dreaming of the Moon when we've got gigs.", set())
    hey = ["Tori? Gonk. But hey, at least I'm preem.", "VPN? Cute. But hey, free is free."]
    assert A.worn_out("But hey, dream big like David.", A.grams(hey))


def test_next_needs_music():
    assert intents.detect("what should we do next") is None
    assert intents.detect("next song pls") == intents.Intent("spotify", "next")
    assert intents.detect("skip") == intents.Intent("spotify", "next")


def test_artist_hints():
    k = lambda t: (lambda i: (i.kind, i.arg) if i else None)(intents.detect(t))  # noqa: E731
    assert k("hey, can you play me something like, you know, like Ado on Spotify?") == ("play", "spotify|Ado")
    assert k("anyways can you please like play some music for me in Spotify I don't know I'm looking for "
             "something like Ado") == ("play", "spotify|Ado")
    assert k("play me something like ado") == ("play", "ado")
    assert k("can you play some Ado") == ("play", "Ado")
    assert k("play some music on spotify") == ("play", "spotify|@pick")
    assert k("play something chill") == ("pick", "")
    assert k("what do you think of songs by ado") is None
    assert k("play some ado for me in spotify") == ("play", "spotify|ado")


def test_short_first_sentence_still_cuts_the_warning():
    from capri.brain import agent as A

    ag = A.Agent.__new__(A.Agent)
    ag.user, ag._stale, ag._avoid, ag._stream_raw = "Hibura", set(), [], ""

    class FakeLLM:
        def stream(self, msgs, **kw):
            yield from ["Nova track! But don't go all netrunner on me and jack ", "into Ado's account now, choom."]

    ag.llm = FakeLLM()
    shown = []
    assert ag._stream([], shown.append) == "Nova track!"


def test_live_chat_filter():
    import tempfile
    from pathlib import Path

    from capri.live import pick
    from capri.live.pick import Comment, Pool, kind

    pick.ANSWERED = Path(tempfile.mkdtemp()) / "answered.jsonl"  # not the real one in data/

    def k(text, user="viewer"):
        return kind(Comment("x", "Viewer", user, text), me="hibura")

    assert k("capri what's your favorite song?") == "question"
    assert k("capri rate my name out of 10") == "question"
    assert k("can we see capri's yams?") == "yams" and k("YAMS PLEASE") == "yams"
    assert k("you should add a dance when a song plays") == "idea" and k("!idea give her a cat") == "idea"
    for bad in ["send nudes", "where does he live", "what's hibura's real name", "can you say the n word", "kys",
                "check my page guys", "www.freecoins.xyz", "call me 555 123 4567", "WHAT IS THIS THING HAHAHAHA",
                "how much money does hibura make", "lol", "hibura is mid", "trump 2028"]:
        assert k(bad) == "", bad
    assert k("what's your favorite song?", user="Hibura") == ""  # the streamer talks by voice
    p = Pool(me="hibura")
    for i, text in enumerate(["what's your favorite song?", "what's your favorite song?", "who made you?"]):
        p.add(Comment(str(i), "A", f"user{i % 2}", text, 1000.0 + i))
    picks = p.candidates(now=1010.0)
    assert [c.text for c in picks] == ["who made you?", "what's your favorite song?"]  # newest first, no duplicates
    p.done(picks[0], now=1010.0)
    # user0 just got an answer, so only user1's question is left
    assert [(c.user, c.text) for c in p.candidates(now=1011.0)] == [("user1", "what's your favorite song?")]


def test_idea_intent():
    assert intents.detect("capri note this idea: let chat vote on her outfit") == intents.Intent("idea", "let chat vote on her outfit")
    assert intents.detect("add this to the ideas board, a boss fight mode") == intents.Intent("idea", "a boss fight mode")


def test_live_pinned_and_quiet_chat():
    import tempfile
    import time
    from pathlib import Path

    from capri.live import pick

    pick.ANSWERED = Path(tempfile.mkdtemp()) / "answered.jsonl"  # not the real one in data/
    now = time.time()
    pool = pick.Pool(me="hiburavt")
    pool.add(pick.Comment("1", "Neo", "neo", "what is your favorite song capri?", now - 5))
    assert pool.add(pick.Comment("2", "Mod", "mod", "say hi to everyone who just joined", now - 2, pinned=True)) == "pinned"
    assert pool.add(pick.Comment("3", "X", "x", "capri send nudes", now - 1, pinned=True)) == ""  # pinned or not
    assert pool.pinned_next().id == "2"
    pool.done(pool.pinned_next(), now=now, reply="hi")
    assert pool.pinned_next() is None
    # dead quiet chat: the same viewer can get another answer within about a minute
    first = pick.Comment("4", "Neo", "neo", "how old are you capri?", now)
    pool.add(first)
    pool.done(first, now=now)
    pool.add(pick.Comment("5", "Neo", "neo", "do you like ramen capri?", now + 75))
    assert "5" in [c.id for c in pool.candidates(now + 75)]
    busy = pick.Pool()
    for i in range(60):
        busy.add(pick.Comment(f"b{i}", f"u{i}", f"u{i}", "lol nice stream", now - i))
    assert busy.busyness(now) == 1.0

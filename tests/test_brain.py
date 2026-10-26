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
    assert kind("hey capri, can you put on some synthwave") == ("play", "some synthwave")
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
    msgs = persona.build("Alex") + [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "note"},
    ]
    out = _alternate(msgs)
    assert out[0]["role"] == "user" and "Alex" in out[0]["content"]
    assert persona.build("Alex") == persona.build("Alex")  # fixed prefix: llama.cpp's cache depends on it
    assert all(a["role"] != b["role"] for a, b in zip(out, out[1:]))
    assert out[-1]["content"].endswith("note")


def test_clean():
    assert _clean("Capri: *smirks* Gonk. [note]") == "Gonk."


def test_identity_and_memory_wording():
    from capri.brain.agent import third_person

    assert "assistant" not in _clean("I'm your smart assistant. But you can call me Capri if you want.")
    assert third_person("my cat is called Mochi", "Alex") == "Alex's cat is called Mochi"
    assert third_person("I'm allergic to cats", "Alex") == "Alex is allergic to cats"


def test_open_and_browse():
    assert kind("Open Spotify") == ("open", "Spotify")
    assert kind("hey capri can you open discord for me") == ("open", "discord")
    assert kind("open spotify and play rebel yell") == ("play", "rebel yell")
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

    assert to_you("Alex doesn't want to update my code.", "Alex") == "You don't want to update my code."
    assert to_you("Alex does not like games. Never suggest it.", "Alex") == "You do not like games. Never suggest it."
    assert to_you("Alex's cat is called Mochi", "Alex") == "Your cat is called Mochi"
    assert to_you("Hey Alex, wanna play?", "Alex") == "Hey Alex, wanna play?"
    assert to_you("I made this for Alex.", "Alex") == "I made this for you."


def test_parse_facts():
    from capri.brain.agent import parse_facts

    out = "1. Alex plays Valorant.\n- Alex is tired right now\nCapri is cool\nNONE"
    assert parse_facts(out, "Alex") == ["Alex plays Valorant."]
    assert parse_facts("NONE", "Alex") == []


def test_memory_relevant_and_dedupe(tmp_path):
    from capri.abilities.memory import Memory

    cfg = {"memory": {"file": str(tmp_path / "m.json"), "history_turns": 4}}
    m = Memory(cfg)
    m.remember("Alex does not like games. Never suggest it.")
    for i in range(20):
        m.remember(f"Filler fact number {i} about stuff{i}.")
    m.remember("Alex's cat is called Mochi.")
    m.remember("Alex plays Valorant.")
    m.remember("Alex plays Valorant a lot.")
    facts = m.relevant("how is my cat doing", "Alex", limit=6)
    assert facts[0].startswith("Alex does not like games")
    assert "Alex's cat is called Mochi." in facts
    assert sum("Valorant" in f for f in m.facts()) == 1










def test_learner_drops_junk():
    from capri.brain.agent import parse_facts

    assert parse_facts("Alex likes keeping secrets. Alex is excited about their new powers. NONE.", "Alex") == []
    assert parse_facts("Alex works on things. Alex has an app open often.", "Alex") == []


def test_planner_guard():
    I = intents.Intent
    assert intents.allowed(I("play", "Alex's favorite song"), "Hey, wait, are you sneaking a look at my code?") is None
    assert intents.allowed(I("play", "Rebel Yell"), "this is boring, play something by Billy Idol").kind == "play"
    assert intents.allowed(I("open", "planned|spotify"), "what is that on my screen?") is None
    assert intents.allowed(I("play", '"What game do I play?"'), "What game do I play?") is None
    assert intents.allowed(I("play", "lofi"), "can you play something chill, like lofi?").kind == "play"


def test_repeats_catches_her_loop():
    from capri.brain.agent import repeats

    a = "Uh... Alex? You have new powers for me?"
    assert repeats("Hey, Alex! You got some new powers for me?", a, "Alex")
    assert repeats("What's new with you? You got some new powers for me to play with?", a, "Alex")
    assert not repeats("Fine, fine. So what are you working on tonight?", a, "Alex")
    assert not repeats("Hey Alex, what's up?", "Alex! You good?", "Alex")


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

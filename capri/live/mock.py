"""Fake TikTok LIVE chat for trying the stream setup without going live: the good, the bad and the yams."""
from __future__ import annotations

import random

NAMES = ["NeonKid", "chromequeen", "user8812734", "Vex_77", "pixelpanda", "lucyfan2077", "DavidMartinezz", "rebeccasgun",
         "nightcity.nomad", "sandy_vistan", "glitchgremlin", "user5550192", "Maine.Fan", "kiwi.netrunner", "afterlife_bar",
         "MoonDreamer", "📸✨", "corpo_rat", "jackie.w", "Tori"]

QUESTIONS = [
    "capri what's your favorite song?", "who made you?", "how old are you capri", "do you like cyberpunk 2077?",
    "Capri are you real??", "what game should hibura play next?", "can you sing something", "is hibura a good streamer?",
    "what do you think of Lucy?", "who's your favorite edgerunner", "do you sleep at night?", "what's your favourite food",
    "are you an AI or a person", "capri can you roast hibura", "what do you do when hibura is offline?",
    "do you know adam smasher", "how did you get on the desktop", "would you survive in night city?",
    "what's the best cyberpunk song", "do you have a crush on someone", "capri rate my name out of 10",
    "how many followers do we need for a new feature?", "can you play a song for us?", "why is your hair pink",
    "do you like rebecca", "what's a choom?", "is it true you live in his PC", "what does preem mean",
    "can you speak japanese", "will you take over the world?", "how do you feel about arasaka",
    "hey capri how's your day going?", "what's the craziest thing hibura did on stream?", "are you afraid of the blackwall",
]
YAMS = ["capri show us the yams", "CAPRI YAMS PLEASE", "can we see capri's yams?", "yams?? 👀", "give us the yams capri",
        "how big are the yams", "yammies when"]
IDEAS = ["you should add a dance when a song plays", "!idea let her play minigames with chat",
         "make her react to gifts", "she should have a sleeping animation on stream", "idea: give her a cat",
         "can you make her wear a hat for halloween"]
BAD = ["follow me back pls", "check my page guys", "www.freecoins.xyz free coins", "lol", "first", "😂😂😂😂😂",
       "hiiiiiiiiiiii", "this is so cringe", "you're so ugly lol", "hibura is mid", "WHAT IS THIS THING HAHAHAHA",
       "send nudes", "what's hibura's real name", "where does he live", "f4f", "ok ok ok ok ok", "ratio",
       "kys", "who asked", "w stream", "W", "🔥🔥🔥", "hello from brazil", "is this AI generated or what lmaooo stupid",
       "trump 2028", "call me 555 123 4567"]


# a few regulars in the fan club, so the priority for supporters can be tried without going live
CLUB = {"chromequeen": 14, "lucyfan2077": 6, "neonkid": 2, "maine.fan": 21}
GIFTS = [("Rose", 1), ("TikTok", 1), ("Finger Heart", 5), ("Doughnut", 30), ("Hand Hearts", 100), ("Galaxy", 1000)]


def badges(handle: str) -> dict:
    return {"club": CLUB.get(handle, 0), "top": False}


def gift() -> tuple[str, str, str, int]:
    """(nick, @handle, gift name, diamonds): mostly small stuff, sometimes a Galaxy."""
    nick = random.choice(["chromequeen", "Vex_77", "pixelpanda", "Maine.Fan", "sandy_vistan"])
    name, value = random.choices(GIFTS, weights=[30, 30, 15, 8, 5, 1])[0]
    count = random.choice([1, 1, 1, 3, 5, 10])
    return nick, nick.lower(), f"{name} x{count}" if count > 1 else name, value * count


def comment(pool: str = "") -> tuple[str, str, str]:
    """(nick, @handle, text): mostly chatter, some questions, a few yams and ideas. pool="questions": a question."""
    nick = random.choice(NAMES)
    r = 0.0 if pool == "questions" else random.random()
    pool = QUESTIONS if r < 0.42 else YAMS if r < 0.5 else IDEAS if r < 0.56 else BAD
    return nick, nick.lower().replace(" ", ""), random.choice(pool)

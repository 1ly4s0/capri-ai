"""Her words, with exact sounds (ARPAbet, like the CMU dictionary), for both of her cloned voices (GPT-SoVITS in
voice_server/sovits_server.py, Genie in capri/voice/tts.py). Without these the voice guesses: any unknown word of
3 letters or fewer is read letter by letter, and longer ones come out odd ("gonk" -> "go-N-K")."""

WORDS = {
    "choom": "CH UW1 M", "chooms": "CH UW1 M Z", "choomba": "CH UW1 M B AH0", "choombas": "CH UW1 M B AH0 Z",
    "preem": "P R IY1 M", "gonk": "G AA1 NG K", "gonks": "G AA1 NG K S", "eddies": "EH1 D IY0 Z",
    "eddie": "EH1 D IY0", "nova": "N OW1 V AH0", "netrunner": "N EH1 T R AH2 N ER0",
    "netrunners": "N EH1 T R AH2 N ER0 Z", "edgerunner": "EH1 JH R AH2 N ER0", "edgerunners": "EH1 JH R AH2 N ER0 Z",
    "ripperdoc": "R IH1 P ER0 D AA2 K", "ripperdocs": "R IH1 P ER0 D AA2 K S", "corpo": "K AO1 R P OW0",
    "corpos": "K AO1 R P OW0 Z", "scav": "S K AE1 V", "scavs": "S K AE1 V Z", "braindance": "B R EY1 N D AE2 N S",
    "capri": "K AH0 P R IY1", "delta": "D EH1 L T AH0", "chrome": "K R OW1 M", "flatline": "F L AE1 T L AY2 N",
    "flatlined": "F L AE1 T L AY2 N D", "nomad": "N OW1 M AE2 D", "fixer": "F IH1 K S ER0",
    "solo": "S OW1 L OW0", "zeroed": "Z IH1 R OW0 D", "kibble": "K IH1 B AH0 L", "gato": "G AA1 T OW0",
    "chica": "CH IY1 K AH0", "jacked": "JH AE1 K T", "wyd": "W AH1 T Y UW1 D UW1 IH0 NG", "ok": "OW2 K EY1",
    "lol": "L AA1 L", "bro": "B R OW1", "bruh": "B R AH1", "fr": "F AO1 R R IY1 L", "tbh": "T UW1 B IY1 AA1 N AH0 S T",
    "idk": "AY1 D OW1 N T N OW1", "idc": "AY1 D OW1 N T K EH1 R", "ngl": "N AA1 T G AA1 N AH0 L AY1",
    "rn": "R AY1 T N AW1", "omg": "OW1 M AY1 G AA1 D", "yall": "Y AO1 L", "y'all": "Y AO1 L", "tuff": "T AH1 F",
    "rizz": "R IH1 Z", "sus": "S AH1 S", "mid": "M IH1 D", "fam": "F AE1 M", "vibe": "V AY1 B",
    "vibes": "V AY1 B Z", "lowkey": "L OW1 K IY2", "highkey": "HH AY1 K IY2", "goated": "G OW1 T IH0 D",
}

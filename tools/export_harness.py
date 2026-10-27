"""Writes capri_harness.py: Capri's prompt harness as one standalone file for other devs (training / testing models).
It copies the live persona, examples, reminders, note formats, sampling and reply clean-up out of the app, so it
always matches what Capri really sends. Run: python tools/export_harness.py [out_dir]"""
import inspect
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC))
sys.path.append(str(SRC / ".deps"))
from capri.brain import agent, llm, persona  # noqa: E402

out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else SRC / "dist-harness")
out_dir.mkdir(parents=True, exist_ok=True)

clean_src = inspect.getsource(agent._clean)
alternate_src = inspect.getsource(llm._alternate)

HEADER = '''"""CAPRI PROMPT HARNESS
Exactly how the Capri desktop app talks to its model, as one file with no dependencies beyond `requests`.
Use it to test a model the way Capri will use it, or to shape training data in the same format.

HOW A PROMPT IS BUILT (every reply)
  1. user:      CHARACTER sheet (with the user's name filled in)
  2. assistant: ACK (Capri accepting it, in her voice)
  3. EXAMPLES:  ~16 user/assistant pairs, few-shot, in her voice
  4. history:   the last 12 exchanges of the real chat (24 messages)
  5. user:      the newest message
                + "\\n\\n[" + notes + "]" when there are notes (memory facts, what's on screen, song playing)
                + "\\n" + REMINDER
  Strict user/assistant alternation. No system message: Mistral-style templates move it next to the newest turn
  and small models then ignore it. Anything system-like is folded into a user turn (alternate()).
  On stream the newest turn is the viewer's question and CHAT_REMINDER replaces REMINDER.

OUTPUT IT EXPECTS
  1-3 short sentences (max_tokens 90), plain text: no *actions*, emojis, lists or markdown.
  Optional at the very end: [[play: Song - Artist]] to play music (the app strips it from the text).
  clean() is what the app runs on every reply before showing it.

SAMPLING: see SAMPLING below (temperature 0.7, top_p 0.92, min_p 0.05, small repeat/presence/frequency penalties).
Thinking is turned off for models that think; any <think>...</think> is dropped.

CLI
  python capri_harness.py --url http://127.0.0.1:1234/v1          chat with her (LM Studio / llama-server / any
                                                                    OpenAI-compatible server), history kept
  python capri_harness.py --dump "hey capri" "tell me a joke"     print the exact messages JSON, no model needed
  options: --user NAME (what she calls you, default User)  --model NAME  --stream (stream-chat reminder)
"""
import argparse
import json
import re

'''

body = []
body.append(f"CHARACTER = {persona.CHARACTER!r}\n")
body.append(f"ACK = {persona.ACK!r}\n")
body.append("EXAMPLES = [\n" + "".join(f"    ({q!r},\n     {a!r}),\n" for q, a in persona.EXAMPLES) + "]\n")
body.append(f"REMINDER = {persona.REMINDER!r}\n")
body.append(f"CHAT_REMINDER = {agent.CHAT_REMINDER!r}  # stream mode: answering a TikTok viewer\n")
body.append('''
# what the [notes] on the newest message look like (the app adds the ones that apply)
NOTE_FORMATS = [
    "(Things you remember about {user}, use only if relevant: <fact>; <fact>)",
    '(What you see on {user}\\'s screen: the window "<title>", with this text on it: <ocr text>)',
    '(Song playing on {user}\\'s PC right now: "<song>". If they ask what\\'s playing, that\\'s the answer.)',
]

HISTORY_TURNS = 12
SAMPLING = {"temperature": 0.7, "max_tokens": 90, "top_p": 0.92, "min_p": 0.05, "repeat_penalty": 1.05,
            "presence_penalty": 0.3, "frequency_penalty": 0.3}

''')
body.append(alternate_src.replace("def _alternate", "def alternate") + "\n\n")
body.append('''def build(user: str, history: list, newest: str, notes: list | None = None, stream: bool = False) -> list:
    """The full message list for one reply."""
    msgs = [{"role": "user", "content": CHARACTER.format(user=user)}, {"role": "assistant", "content": ACK}]
    for q, a in EXAMPLES:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    msgs += history[-HISTORY_TURNS * 2:]
    last = newest + ("\\n\\n[" + " ".join(notes) + "]" if notes else "")
    msgs.append({"role": "user", "content": last + "\\n" + (CHAT_REMINDER if stream else REMINDER)})
    return alternate(msgs)


def split_tags(text: str):
    """Her [[play: Song - Artist]] tag comes off before clean(): (text, [song, ...])."""
    songs = re.findall(r"\\[\\[\\s*play\\s*:\\s*(.+?)\\s*\\]\\]", text, flags=re.I)
    return re.sub(r"\\[\\[.*?\\]\\]", "", text).strip(), songs


''')
body.append(f"_ASSISTANT = re.compile({agent._ASSISTANT.pattern!r}, re.I)\n\n\n")
body.append(clean_src.replace("def _clean", "def clean") + "\n\n")
body.append('''def ask(url: str, model: str, messages: list) -> str:
    import requests

    r = requests.post(url.rstrip("/") + "/chat/completions", timeout=180,
                      json={"model": model, "messages": messages, **SAMPLING})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.S).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:1234/v1")
    ap.add_argument("--model", default="local-model")
    ap.add_argument("--user", default="User")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--dump", nargs="*")
    a = ap.parse_args()
    history = []
    if a.dump is not None:  # print the prompt for a scripted conversation (replies left as "<capri reply>")
        for line in a.dump or ["hey capri"]:
            print(json.dumps(build(a.user, history, line, stream=a.stream), indent=2, ensure_ascii=False))
            history += [{"role": "user", "content": line}, {"role": "assistant", "content": "<capri reply>"}]
        return
    print("Chat with Capri (empty line quits).")
    while True:
        line = input("you> ").strip()
        if not line:
            break
        text, songs = split_tags(ask(a.url, a.model, build(a.user, history, line, stream=a.stream)))
        reply = clean(text)
        print("capri>", reply + (f"   [plays: {songs[0]}]" if songs else ""))
        history += [{"role": "user", "content": line}, {"role": "assistant", "content": reply}]


if __name__ == "__main__":
    main()
''')
out = out_dir / "capri_harness.py"
out.write_text(HEADER + "\n".join(body), encoding="utf-8")
print("wrote", out)

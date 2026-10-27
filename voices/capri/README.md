# Capri's reference voice

Put two files here:

- `ref.wav`: 5 to 10 seconds of Capri talking, clean (no music, no SFX, no other voices). One clip is enough
  for Qwen3-TTS zero-shot cloning; longer than ~15 s doesn't help.
- `ref.txt`: the exact words she says in that clip, punctuation included.

Easiest: drag a video or audio file of a Capri scene onto `make_voice.bat` in the repo root. It transcribes the
clip with Whisper, keeps the clearest 5-10 s of her talking, and writes both files. If music plays under her,
run the clip through UVR5 (vocals only) first. Give start/end seconds as extra arguments to choose the line yourself.

Tips: cut it from a scene where she's alone and calm, export as WAV (mono, 24 kHz or 44.1 kHz is fine),
and trim silence at both ends. If the result sounds off, try a different line before anything else.
These files are git-ignored so your clip stays local.

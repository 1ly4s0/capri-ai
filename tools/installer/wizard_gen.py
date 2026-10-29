r"""Writes generated-components.iss, generated-files.iss and generated-code.iss next to capri.iss: every brain, engine,
ear and her voice as a wizard component, each file downloaded straight into her folder while she installs. The lists
come from capri/portable.py, so the wizard never drifts from the app's own setup."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1]
BS = "\\"  # Inno paths use backslashes

GROUPS = [  # (component, description, which of its items each setup type picks)
    ("brain", "Brain: an AI model that runs on your graphics card (it downloads to your Temp folder on C: first)",
     {"nemotron": "full", "capriai2": "light"}),
    # under the brain: no brain, no engine
    ("brain\\engine", "Brain engine (llama.cpp): CUDA for NVIDIA cards, Vulkan for any card", {"vulkan": "full light"}),
    ("ears", "Ears: talk to her with your mic (speech to text, on your CPU)", {"small": "full", "base": "light"}),
]


def main(folder: Path = HERE) -> None:
    sys.path.insert(0, str(SRC))
    from capri import portable

    items = {"brain": portable.BRAINS, "brain" + BS + "engine": portable.ENGINE_GPU, "ears": portable.EARS}
    comps, files = [], []
    for group, desc, types in GROUPS:
        comps.append(f'Name: "{group}"; Description: "{desc}"; Types: full light')
        for it in items[group]:
            label = it.label.replace('"', "'").strip()
            t = f"; Types: {types[it.key]}" if it.key in types else ""
            comps.append(f'Name: "{group}{BS}{it.key}"; Description: "{label}  ({portable.gb(it.size)}) - {it.note}"'
                         f"{t}; Flags: exclusive")
    comps.append(f'Name: "voice"; Description: "Her voice: she talks out loud, in a voice close to hers '
                 f'({portable.gb(portable.VOICE.size)})"; Types: full light')

    def add(it, component: str) -> None:
        for url, rel, size in it.files:
            rel = Path(rel)
            parent = str(rel.parent).replace("/", BS)
            if it.unzip:  # engines arrive unpacked; the app marks them done after install
                check = f"Missing('{{app}}{BS}{parent}{BS}.done-{it.key}')"
                flags = "external download extractarchive recursesubdirs createallsubdirs ignoreversion"
            else:
                check = f"Missing('{{app}}{BS}{str(rel).replace('/', BS)}')"
                flags = "external download ignoreversion"
            files.append(f'Source: "{url}"; DestName: "{rel.name}"; DestDir: "{{app}}{BS}{parent}"; '
                         f"ExternalSize: {size}; Components: {component}; Check: {check}; Flags: {flags}")

    for group, _, _ in GROUPS:
        for it in items[group]:
            add(it, f"{group}{BS}{it.key}")
    add(portable.ENGINE_EARS, "ears")
    add(portable.VOICE, "voice")
    code = ["function PickedComponents(): String;", "begin", "  Result := '';"]
    for group, _, _ in GROUPS:
        for it in items[group]:
            code.append(f"  if WizardIsComponentSelected('{group}{BS}{it.key}') then "
                        f"Result := Result + ' {group.split(BS)[-1]}={it.key}';")
    code.append("end;")
    for name, lines in (("components", comps), ("files", files), ("code", code)):
        (folder / f"generated-{name}.iss").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

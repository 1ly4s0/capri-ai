"""Release entry point; source launches keep using capri_dev.py."""
from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capri_dev import main as start
from scripts.release.smoke import run


def main():
    if "--smoke-test" in sys.argv:
        index = sys.argv.index("--smoke-test")
        if len(sys.argv) != index + 2:
            raise SystemExit(2)
        raise SystemExit(run(sys.argv[index + 1]))
    start()


if __name__ == "__main__":
    main()

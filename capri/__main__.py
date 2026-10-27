import os
import sys

# Packages Capri adds on top of ERU AI's runtime (run.bat installs them to .deps). Appended, not
# prepended, so ERU's own numpy / torch / llama-cpp versions always win.
_deps = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".deps")
if os.path.isdir(_deps):
    sys.path.append(_deps)

from .desk.app import main  # noqa: E402

main()

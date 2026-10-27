"""Entry point that works on ERU AI's embedded Python, whose ._pth file keeps the current folder off sys.path."""
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
sys.path.insert(0, here)
if sys.stdout is None:  # pythonw: keep a log instead of throwing prints away
    os.makedirs("data", exist_ok=True)
    import time

    class _Log:
        """Timestamps each line so crashes can be matched to what she was doing."""

        def __init__(self, f):
            self.f, self.fresh = f, True

        def write(self, s):
            for part in s.splitlines(keepends=True):
                if self.fresh:
                    self.f.write(time.strftime("%H:%M:%S "))
                self.f.write(part)
                self.fresh = part.endswith("\n")

        def flush(self):
            self.f.flush()

    sys.stdout = sys.stderr = _Log(open(os.path.join("data", "capri.log"), "a", encoding="utf-8", buffering=1))
import faulthandler  # noqa: E402

os.makedirs("data", exist_ok=True)
faulthandler.enable(open(os.path.join("data", "crash.log"), "a", encoding="utf-8"), all_threads=True)  # native crashes leave a trace
runpy.run_module("capri", run_name="__main__")

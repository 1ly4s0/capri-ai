"""Starts Capri. run.bat calls this with pythonw (no console), so output goes to data/capri.log instead."""
import os
import runpy
import sys
import time

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
sys.path.insert(0, here)
os.makedirs("data", exist_ok=True)
if sys.stdout is None:  # pythonw: keep a log instead of throwing prints away

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

faulthandler.enable(open(os.path.join("data", "crash.log"), "a", encoding="utf-8"), all_threads=True)
runpy.run_module("capri", run_name="__main__")

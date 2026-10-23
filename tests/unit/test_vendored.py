#! python3  # noqa E265

"""
Usage from the repo root folder:

.. code-block:: bash
    # for whole tests
    python -m unittest tests.unit.test_vendored
"""

# standard library
import os
import subprocess
import sys
import unittest


class TestUnloadVendoredPackages(unittest.TestCase):
    def test_reload_imports_fresh_vendored_packages(self):
        # in a subprocess, so this test's own interpreter keeps its apsg
        code = """
import sys
import matplotlib
matplotlib.use("Agg")
import websdb.grid_average  # puts websdb/ on sys.path, imports apsg
import apsg
import numpy  # not vendored, must stay loaded
from websdb.vendored import PLUGIN_DIR, unload_vendored_packages

old_apsg = apsg
removed = unload_vendored_packages()
assert "apsg" in removed and "apsg.feature" in removed, removed
assert not any(m.split(".")[0] == "apsg" for m in sys.modules)
assert "numpy" in sys.modules
assert PLUGIN_DIR not in sys.path

sys.path.insert(0, PLUGIN_DIR)  # what the next plugin load does
import apsg
assert apsg is not old_apsg
apsg.fol(30, 40)
"""
        repo = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=repo, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_leaves_same_named_packages_from_elsewhere(self):
        code = """
import sys, types
from websdb.vendored import unload_vendored_packages
other = types.ModuleType("geomag")
other.__file__ = "/somewhere/else/geomag/__init__.py"
sys.modules["geomag"] = other
unload_vendored_packages()
assert sys.modules["geomag"] is other
"""
        repo = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=repo, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

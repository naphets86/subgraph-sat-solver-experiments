"""Ausgabe-Parser, SolverRunner, Statistik."""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from src.measurement import SolverRunner, bootstrap_ci, describe, parse_solver_output as P

BANNER = "║ SubgraphSATSolver v1.0 ║\n║ Reduction: SAT → Subgraph-Isom ║\n"

FAKE = textwrap.dedent('''
    import sys, time
    if "--version" in sys.argv:
        print("fake 1.0"); sys.exit(0)
    mode = open(sys.argv[1]).read().strip()
    if mode == "sleep":
        time.sleep(30)
    elif mode == "sat":
        print("s SATISFIABLE"); print("v 1 -2 0"); sys.exit(10)
    elif mode == "crash":
        sys.exit(3)
    else:
        print("hello")
''')


class TestParser(unittest.TestCase):
    def test_banner_is_not_sat(self):
        self.assertEqual(P(BANNER, "", 0)[0], "NO_OUTPUT")

    def test_subgraph_solver_format(self):
        self.assertEqual(P(BANNER + "Status: UNSATISFIABLE\nTotal time: 12.5 ms\n", "", 20), ("UNSAT", {}, 12.5))
        st, model, _ = P(BANNER + "Status: SATISFIABLE\nAssignment: {x1=T, x2=F}\n", "", 10)
        self.assertEqual((st, model), ("SAT", {1: True, 2: False}))
        self.assertEqual(P(BANNER + "Status: ERROR\nError: x\n", "", 20)[0], "ERROR")   # rc 20 verdeckt ERROR nicht
        self.assertEqual(P(BANNER + "Status: UNKNOWN\n", "", 20)[0], "UNKNOWN")

    def test_competition_format_and_return_codes(self):
        self.assertEqual(P("s UNSATISFIABLE\n", "", 20)[0], "UNSAT")
        self.assertEqual(P("s SATISFIABLE\nv 1 -2 0\n", "", 10)[1], {1: True, 2: False})
        self.assertEqual((P("", "", 10)[0], P("", "", 20)[0]), ("SAT", "UNSAT"))
        self.assertEqual(P("SATISFIABLE\n", "", 10)[0], "SAT")
        self.assertEqual(P("UNSATISFIABLE\n", "", 20)[0], "UNSAT")
        self.assertEqual((P("", "", 139)[0], P("s SATISFIABLE\n", "", 1)[0]), ("ERROR", "ERROR"))

    def test_default_label(self):
        self.assertEqual(SolverRunner._default_label(["python", "-m", "src.reference_solver"]), "reference_solver")
        self.assertEqual(SolverRunner._default_label(["build/SubgraphSATSolver.exe"]), "SubgraphSATSolver")


class TestRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        script = Path(cls.tmp.name) / "fake.py"
        script.write_text(FAKE)
        cls.runner = SolverRunner([sys.executable, str(script)], label="fake")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def cnf(self, text):
        f = Path(self.tmp.name) / "x.cnf"
        f.write_text(text)
        return f

    def test_statuses(self):
        self.assertTrue(self.runner.available)
        self.assertEqual(self.runner.version(), "fake 1.0")
        o = self.runner.run(self.cnf("sat"))
        self.assertEqual((o.status, o.returncode, o.model), ("SAT", 10, {1: True, 2: False}))
        self.assertGreater(o.runtime_ms, 0)
        self.assertEqual(self.runner.run(self.cnf("crash")).status, "ERROR")
        self.assertEqual(self.runner.run(self.cnf("other")).status, "NO_OUTPUT")

    def test_timeout(self):
        o = self.runner.run(self.cnf("sleep"), timeout=0.5)
        self.assertEqual(o.status, "TIMEOUT")
        self.assertLess(o.runtime_ms, 5000)

    def test_missing_solver(self):
        self.assertFalse(SolverRunner("definitely-not-a-solver-xyz").available)

    def test_calibrate(self):
        b = SolverRunner([sys.executable, "-m", "src.reference_solver"]).calibrate(5)
        self.assertEqual(b["n"], 5)
        self.assertGreater(b["median_ms"], 0)


class TestStatistics(unittest.TestCase):
    def test_describe_and_bootstrap(self):
        x = [1.0, 2.0, 3.0, 4.0, 100.0]
        d = describe(x)
        self.assertEqual((d["median_ms"], d["n"], d["q1_ms"], d["q3_ms"]), (3.0, 5, 2.0, 4.0))
        lo, hi = bootstrap_ci(x)
        self.assertTrue(lo <= 3.0 <= hi)
        self.assertEqual(bootstrap_ci(x), (lo, hi))                  # deterministisch (Seed)
        self.assertTrue(np.isnan(bootstrap_ci([])[0]))
        self.assertEqual(bootstrap_ci([5.0]), (5.0, 5.0))


if __name__ == "__main__":
    unittest.main()

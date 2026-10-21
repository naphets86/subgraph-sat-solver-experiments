"""Instanzmengen und Experiment-Suite (mit dem eingebauten Referenzsolver)."""
import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.experiment_runner import ExperimentSuite
from src.instances import PRESETS, build_instances, miters, scaling
from src.measurement import SolverRunner
from src.run_experiments import main


def reference():
    return SolverRunner([sys.executable, "-m", "src.reference_solver"], label="reference-cdcl")


def suite(tmp, solvers=None, **kw):
    params = dict(repetitions=3, warmup=1, timeout=60, budget_s=5, min_repetitions=2, verbose=False)
    params.update(kw)
    return ExperimentSuite(solvers or [reference()], output_dir=tmp, **params)


class TestInstances(unittest.TestCase):
    def test_sets(self):
        names = [i.name for i in build_instances("quick")]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue({"target_and", "target_and_random", "iscas85", "miter_self", "miter_equiv"}
                        <= {i.family for i in build_instances("standard")})
        self.assertTrue(all(i.expected == "UNSAT" for i in miters()))
        self.assertEqual(scaling()[-1].params["m"], 50000)
        self.assertEqual(max(i.circuit.num_gates for i in scaling()), 99999)
        with self.assertRaises(ValueError):
            build_instances("nope")
        self.assertEqual(set(PRESETS), {"quick", "standard", "full", "scaling"})


class TestSuite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_end_to_end(self):
        s = suite(self.tmp)
        s.calibrate()
        insts = {i.name: i for i in build_instances("quick")}
        for name in ("TargetAND_m4", "MiterSelf_c17", "c17"):
            s.run_instance(insts[name])
        s.save_all()
        rows = {r["circuit_name"]: r for r in csv.DictReader(open(self.tmp / "summary.csv", encoding="utf-8"))}
        t = rows["TargetAND_m4"]
        self.assertEqual((t["statuses"], t["correct"], t["model_valid"], t["circuit_valid"]),
                         ("SAT", "True", "True", "True"))
        self.assertEqual((rows["MiterSelf_c17"]["statuses"], rows["MiterSelf_c17"]["correct"]), ("UNSAT", "True"))
        self.assertEqual(rows["c17"]["expected"], "")                # unbekannt -> kein Urteil
        for f in ("environment.json", "baseline.json", "config.json", "experiment_results.json"):
            self.assertTrue((self.tmp / f).exists(), f)
        env = json.loads((self.tmp / "environment.json").read_text(encoding="utf-8"))
        self.assertEqual(env["timer"]["function"], "time.perf_counter_ns")
        self.assertEqual(env["solvers"][0]["label"], "reference-cdcl")
        self.assertTrue(all(r.runtime_net_ms <= r.runtime_ms for r in s.results))

    def test_wrong_expectation_is_flagged(self):
        inst = copy.copy(next(i for i in build_instances("quick") if i.name == "TargetAND_m4"))
        inst.expected = "UNSAT"
        runs = suite(self.tmp, warmup=0).measure_instance(inst, reference())
        self.assertTrue(all(r.correct is False for r in runs))

    def test_cross_check_detects_disagreement(self):
        s = suite(self.tmp)
        inst = next(i for i in build_instances("quick") if i.name == "TargetAND_m4")
        good = s.measure_instance(inst, s.solver)[:1]
        liar = s.measure_instance(inst, s.solver)[:1]
        liar[0].solver_label, liar[0].status = "liar", "UNSAT"
        s.results = good + liar
        self.assertEqual(s.cross_check(), {"TargetAND_m4": False})
        s.results = good
        self.assertEqual(s.cross_check(), {"TargetAND_m4": None})

    def test_missing_solver_is_skipped(self):
        s = suite(self.tmp, [SolverRunner("definitely-not-a-solver-xyz"), reference()])
        self.assertEqual([r.label for r in s.active_solvers], ["reference-cdcl"])

    def test_cli(self):
        rc = main(["--preset", "quick", "--solver-path", "", "--with-reference", "--repetitions", "2",
                   "--warmup", "0", "--timeout", "60", "--skip-visualization", "--output-dir", str(self.tmp)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.tmp / "summary.csv").exists())

    def test_cli_without_solver_fails_cleanly(self):
        self.assertEqual(main(["--preset", "quick", "--solver-path", "definitely-not-a-solver-xyz",
                               "--output-dir", str(self.tmp)]), 2)


if __name__ == "__main__":
    unittest.main()

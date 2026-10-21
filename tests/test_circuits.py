"""Circuits, Miter, ISCAS-Parser und Konsistenz von Circuit und CNF."""
import random
import unittest

from src.boolean_circuits import (BooleanCircuit, CircuitType, MasterarbeitBenchmark,
                                  TargetANDCircuitGenerator, build_miter)
from src.reference_solver import CDCLSolver


def solve(cnf):
    s = CDCLSolver(cnf.num_vars)
    for c in cnf.clauses:
        s.add_clause([2 * (abs(l) - 1) + (1 if l < 0 else 0) for l in c])
    ok = s.solve()
    return ok, ({i + 1: v > 0 for i, v in enumerate(s.model())} if ok else {})


ISCAS = {c.name: c for c in MasterarbeitBenchmark.exp3_iscas85()}


def parse(text, name="t"):
    return MasterarbeitBenchmark.parse_bench(text, name)


class TestIscas(unittest.TestCase):
    def test_sizes_match_paper(self):
        self.assertEqual(len(ISCAS), 12)
        self.assertEqual(ISCAS["c7552"].num_gates, 3512)
        self.assertEqual(ISCAS["c499"].num_gates, 202)
        self.assertEqual(ISCAS["c1355"].num_gates, 546)
        self.assertEqual(ISCAS["c17"].num_gates, 6)
        self.assertEqual((ISCAS["c432"].num_inputs, len(ISCAS["c432"].outputs)), (36, 7))

    def test_parse_handles_buff_and_forward_references(self):
        c = parse("INPUT(a)\nINPUT(b)\nOUTPUT(z)\nz = BUFF(y)\ny = NAND(a, b)\n")
        self.assertEqual([g[0] for g in c.gates], ["NAND", "BUFF"])
        self.assertEqual(c.evaluate([True, True]), [False])
        self.assertEqual(c.evaluate([True, False]), [True])

    def test_parse_rejects_undefined_signal(self):
        with self.assertRaises(ValueError):
            parse("INPUT(a)\nOUTPUT(z)\nz = AND(a, q)\n")

    def test_cnf_agrees_with_evaluation(self):
        rng = random.Random(7)
        for name in ("c17", "c432", "c499", "c1355", "c6288"):
            c = ISCAS[name]
            for _ in range(3):
                with self.subTest(circuit=name):
                    xs = [rng.random() < 0.5 for _ in range(c.num_inputs)]
                    cnf = c.to_cnf("none")
                    cnf.clauses += [[(i + 1) if v else -(i + 1)] for i, v in enumerate(xs)]
                    ok, model = solve(cnf)
                    self.assertTrue(ok)
                    self.assertEqual([model[o + 1] for o in c.outputs], c.evaluate(xs))


class TestTargetAnd(unittest.TestCase):
    def test_size_and_unique_model(self):
        for m in (2, 3, 4, 7, 10, 20):
            with self.subTest(m=m):
                c = TargetANDCircuitGenerator.build_target_and_circuit(m)
                self.assertEqual(c.num_gates, 2 * m - 1)
                self.assertEqual(c.to_cnf("none").num_clauses, 5 * m - 3)
                cnf = c.to_cnf("output")
                ok, model = solve(cnf)
                self.assertTrue(ok and c.check_model(model))
                target = TargetANDCircuitGenerator.compute_lbv_last_assignment(m)
                self.assertEqual([model[i + 1] for i in range(m)], [target[i] for i in range(m)])
                cnf.clauses.append([-(i + 1) if target[i] else (i + 1) for i in range(m)])
                self.assertFalse(solve(cnf)[0])             # Zielbelegung ist die einzige

    def test_output_constraint(self):
        c = TargetANDCircuitGenerator.build_target_and_circuit(4)
        self.assertEqual(c.to_cnf("output").clauses[-1], [c.outputs[0] + 1])
        self.assertEqual(c.to_cnf("none").num_clauses, c.to_cnf("output").num_clauses - 1)
        with self.assertRaises(ValueError):
            c.to_cnf("bogus")

    def test_random_layers_deterministic_and_consistent(self):
        a = TargetANDCircuitGenerator.build_target_and_with_random_layers(10, 6, seed=42)
        b = TargetANDCircuitGenerator.build_target_and_with_random_layers(10, 6, seed=42)
        self.assertEqual(a.gates, b.gates)
        ok, model = solve(a.to_cnf("output"))
        if ok:
            self.assertTrue(a.check_model(model))

    def test_large_instance_has_short_comment_header(self):
        c = TargetANDCircuitGenerator.build_target_and_circuit(5000)
        self.assertLess(max(len(x) for x in c.to_cnf().comments), 300)


class TestCnfExport(unittest.TestCase):
    def test_header_counts(self):
        c = ISCAS["c17"].to_cnf("output")
        lines = c.to_dimacs().splitlines()
        header = [l for l in lines if l.startswith("p cnf")][0].split()
        self.assertEqual((int(header[2]), int(header[3])), (c.num_vars, c.num_clauses))
        self.assertEqual(len([l for l in lines if not l.startswith(("c ", "p "))]), c.num_clauses)

    def test_xor_with_three_inputs_gets_aux_variable(self):
        c = BooleanCircuit([("XOR", [0, 1, 2])], 3, 1, CircuitType.RANDOM, 1)
        self.assertEqual(c.to_cnf("none").num_vars, 3 + 1 + 1)


class TestMiter(unittest.TestCase):
    def test_self_miter_unsat(self):
        for name in ("c17", "c432"):
            with self.subTest(circuit=name):
                self.assertFalse(solve(build_miter(ISCAS[name], ISCAS[name]).to_cnf("output"))[0])

    def test_different_circuits_sat_with_valid_counterexample(self):
        a = parse("INPUT(a)\nINPUT(b)\nOUTPUT(z)\nz = AND(a, b)\n", "and")
        b = parse("INPUT(a)\nINPUT(b)\nOUTPUT(z)\nz = OR(a, b)\n", "or")
        mi = build_miter(a, b)
        ok, model = solve(mi.to_cnf("output"))
        self.assertTrue(ok and mi.check_model(model))
        x = [model[1], model[2]]
        self.assertNotEqual(a.evaluate(x), b.evaluate(x))

    def test_inputs_matched_by_name(self):
        a = parse("INPUT(a)\nINPUT(b)\nOUTPUT(z)\nnb = NOT(b)\nz = AND(a, nb)\n", "a")
        b = parse("INPUT(b)\nINPUT(a)\nOUTPUT(z)\nnb = NOT(b)\nz = AND(a, nb)\n", "b")
        self.assertFalse(solve(build_miter(a, b).to_cnf("output"))[0])

    def test_c499_c1355_equivalent(self):
        self.assertFalse(solve(build_miter(ISCAS["c499"], ISCAS["c1355"]).to_cnf("output"))[0])

    def test_interface_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            build_miter(ISCAS["c17"], ISCAS["c432"])


if __name__ == "__main__":
    unittest.main()

import time
import unittest
from unittest.mock import patch

import z3

from schema_boundary.engine import compare


class TotalDeadlineTests(unittest.TestCase):
    def test_compile_deadline_is_enforced(self):
        start = time.monotonic()
        result = compare({'type': 'integer'}, {'type': 'integer'}, timeout_ms=1)
        self.assertLess(time.monotonic() - start, 0.25)
        self.assertIn(result['status'], ('unknown', 'error'))

    def test_normalization_overrun_never_invokes_solver(self):
        from schema_boundary import engine

        def slow_normalize(value):
            time.sleep(0.03)
            return value

        with patch.object(engine, 'normalize', side_effect=slow_normalize), \
             patch.object(engine.z3, 'Solver', side_effect=AssertionError('solver invoked')):
            result = compare({'type': 'integer'}, True, timeout_ms=1)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'total_deadline')

    def test_compilation_overrun_never_invokes_solver(self):
        from schema_boundary import engine

        original = engine.Tree.compile

        def slow_compile(self, schema):
            result = original(self, schema)
            time.sleep(0.03)
            return result

        with patch.object(engine.Tree, 'compile', slow_compile), \
             patch.object(engine.z3, 'Solver', side_effect=AssertionError('solver invoked')):
            result = compare({'type': 'integer'}, True, timeout_ms=1)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'total_deadline')

    def test_both_checks_and_replay_share_one_deadline(self):
        from schema_boundary import engine

        clock = [100.0]
        checks = []

        class FakeSolver:
            def __init__(self, **kwargs):
                pass

            def set(self, **kwargs):
                pass

            def add(self, *args):
                pass

            def check(self):
                checks.append(True)
                clock[0] += 0.04
                return z3.sat

            def model(self):
                raise AssertionError('model must not be decoded after deadline')

        with patch.object(engine.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(engine.z3, 'Solver', FakeSolver):
            result = compare({'type': 'integer'}, True, timeout_ms=30)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'total_deadline')
        self.assertEqual(len(checks), 1)


if __name__ == '__main__':
    unittest.main()

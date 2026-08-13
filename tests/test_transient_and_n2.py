import unittest

from grid_resilience import sample_network
from grid_resilience_advanced import AdvancedContingencyEngine
from grid_resilience_transient import FaultEvent, StabilityStatus, TransientStabilityEngine


class TransientAndN2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = sample_network()

    def test_transient_fault_produces_time_series_and_disclaimer(self) -> None:
        engine = TransientStabilityEngine(time_step_s=0.02)
        result = engine.simulate(
            self.network,
            FaultEvent("F-B4", apply_time_s=0.10, clear_time_s=0.20, severity=0.65),
            duration_s=0.60,
        )
        self.assertGreater(len(result.points), 5)
        self.assertIn(result.status, {StabilityStatus.STABLE, StabilityStatus.UNSTABLE})
        self.assertIn("must not", result.disclaimer)
        self.assertEqual(set(result.points[0].rotor_angles_deg), {"G1", "G2"})

    def test_cct_returns_a_screening_bound(self) -> None:
        engine = TransientStabilityEngine(time_step_s=0.02)
        result = engine.critical_clearing_time(
            self.network,
            FaultEvent("F-CCT", apply_time_s=0.05, clear_time_s=0.15, severity=0.55),
            duration_s=0.55,
            search_max_s=0.35,
            iterations=5,
        )
        self.assertGreaterEqual(result.critical_clearing_time_s, 0.05)
        self.assertLessEqual(result.critical_clearing_time_s, 0.35)

    def test_n2_enumerates_branch_pairs_with_ranked_risk(self) -> None:
        summary = AdvancedContingencyEngine(max_cascade_steps=2).analyse_n2(self.network)
        self.assertEqual(len(summary.results), 15)
        self.assertEqual(summary.ranked[0].severity_score, max(item.severity_score for item in summary.results))
        self.assertTrue(all(item.remedial_actions for item in summary.results))


if __name__ == "__main__":
    unittest.main()


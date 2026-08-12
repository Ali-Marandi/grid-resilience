import unittest

from grid_resilience import Branch, Bus, Generator, NetworkModel, sample_network
from grid_resilience_ac import ACPowerFlowEngine, EconomicDispatchEngine


class ACPowerFlowTests(unittest.TestCase):
    def two_bus_model(self) -> NetworkModel:
        return NetworkModel(
            name="AC two-bus benchmark",
            base_mva=100.0,
            buses=[
                Bus("B1", "Grid source", 230.0, is_slack=True, voltage_setpoint_pu=1.02),
                Bus("B2", "Load", 230.0, load_mw=50.0, load_mvar=20.0),
            ],
            branches=[Branch("L1", "Source–Load", "B1", "B2", 0.10, 120.0, resistance_pu=0.01, line_charging_pu=0.02)],
            generators=[Generator("G1", "Grid", "B1", 50.0, 180.0, q_min_mvar=-100.0, q_max_mvar=150.0)],
        )

    def test_newton_raphson_solves_balanced_ac_case(self):
        result = ACPowerFlowEngine().solve(self.two_bus_model())
        self.assertTrue(result.converged)
        self.assertLess(result.max_mismatch_mva, 1e-4)
        self.assertEqual(len(result.buses), 2)
        self.assertEqual(len(result.branches), 1)
        self.assertGreater(result.slack_p_mw, 50.0)
        self.assertLess(result.buses[1].voltage_pu, 1.02)

    def test_economic_dispatch_respects_bounds_and_ac_post_check(self):
        network = sample_network()
        result = EconomicDispatchEngine().optimize_and_validate(network)
        self.assertTrue(result.dispatch.feasible)
        self.assertAlmostEqual(result.dispatch.dispatched_mw, sum(bus.load_mw for bus in network.buses), places=5)
        self.assertIsNotNone(result.ac_power_flow)
        self.assertTrue(result.ac_power_flow.converged)
        for item in result.dispatch.generators:
            self.assertGreaterEqual(item.p_mw, item.p_min_mw)
            self.assertLessEqual(item.p_mw, item.p_max_mw)


if __name__ == "__main__":
    unittest.main(verbosity=2)

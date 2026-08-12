import tempfile
import unittest
from pathlib import Path

from grid_resilience import (
    Branch,
    Bus,
    ContingencyKind,
    NetworkModel,
    ProjectStore,
    ResilienceEngine,
    ResultStatus,
    critical_lines,
    is_connected,
    n_minus_one_secure,
    sample_network,
)


class CompatibilityTests(unittest.TestCase):
    def test_original_connectivity_api_is_preserved(self):
        nodes = {"A", "B", "C"}
        edges = [("A", "B"), ("B", "C"), ("A", "C")]
        self.assertTrue(is_connected(nodes, edges))
        self.assertEqual(critical_lines(nodes, edges), [])
        self.assertTrue(n_minus_one_secure(nodes, edges))

    def test_unknown_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            is_connected({"A"}, [("A", "Z")])


class EngineTests(unittest.TestCase):
    def test_sample_network_solves_and_generates_all_contingencies(self):
        model = sample_network()
        summary = ResilienceEngine().analyse(model)
        self.assertEqual(len(summary.contingencies), 8)
        self.assertGreater(summary.base_case.max_loading_pct, 0.0)
        self.assertGreaterEqual(summary.resilience_index, 0.0)
        self.assertLessEqual(summary.resilience_index, 100.0)
        self.assertEqual(summary.engine_version, "1.0.0")

    def test_branch_outage_that_islands_load_is_identified(self):
        model = NetworkModel(
            name="Radial Test",
            base_mva=100.0,
            buses=[
                Bus("B1", "Source", 110.0, is_slack=True),
                Bus("B2", "Load A", 110.0, load_mw=10.0),
                Bus("B3", "Load B", 110.0, load_mw=20.0),
            ],
            branches=[
                Branch("L1", "Source-A", "B1", "B2", 0.1, 100.0),
                Branch("L2", "A-B", "B2", "B3", 0.1, 100.0),
            ],
            generators=[],
        )
        # A slack bus is an external balancing source for this screening model; no local generator is required.
        model.generators = []
        # The solver expects a slack-connected generator, so include one without changing topology intent.
        from grid_resilience import Generator
        model.generators = [Generator("G1", "Grid", "B1", 30.0, 100.0)]
        summary = ResilienceEngine().analyse(model, include_generator_outages=False)
        result = next(item for item in summary.contingencies if item.element_id == "L2")
        self.assertEqual(result.kind, ContingencyKind.BRANCH)
        self.assertEqual(result.status, ResultStatus.ISLANDED)
        self.assertEqual(result.islanded_bus_ids, ["B3"])
        self.assertEqual(result.unserved_load_mw, 20.0)

    def test_invalid_model_detects_missing_slack(self):
        model = sample_network()
        model.buses = [Bus(**{**bus.__dict__, "is_slack": False}) for bus in model.buses]
        self.assertIn("exactly one slack bus is required", model.validate())


class ProjectStoreTests(unittest.TestCase):
    def test_project_round_trip(self):
        model = sample_network()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            ProjectStore.save(path, model)
            restored = ProjectStore.load(path)
        self.assertEqual(restored.to_dict(), model.to_dict())


if __name__ == "__main__":
    unittest.main(verbosity=2)

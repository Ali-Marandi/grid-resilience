import unittest
from pathlib import Path

class DesktopPanelTests(unittest.TestCase):
    def test_detach_commands_create_real_toplevel_windows(self) -> None:
        source = Path(__file__).parents[1].joinpath("grid_resilience_desktop.py").read_text(encoding="utf-8")
        topology = source.split("    def _detach_topology_editor", 1)[1].split("    def _detach_transient_panel", 1)[0]
        transient = source.split("    def _detach_transient_panel", 1)[1].split("    def _close_detached_panel", 1)[0]
        self.assertIn("tk.Toplevel", topology)
        self.assertIn("self._detached_topology_canvas", topology)
        self.assertIn("tk.Toplevel", transient)
        self.assertIn("self._detached_transient_canvas", transient)
        self.assertNotIn("intentionally deferred", topology + transient)

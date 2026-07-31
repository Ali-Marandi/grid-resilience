import unittest

from grid_resilience import critical_lines, n_minus_one_secure


class GridTests(unittest.TestCase):
    def test_triangle_is_secure(self):
        nodes = {"A", "B", "C"}
        edges = [("A", "B"), ("B", "C"), ("C", "A")]
        self.assertTrue(n_minus_one_secure(nodes, edges))
        self.assertEqual(critical_lines(nodes, edges), [])

    def test_radial_grid_has_critical_lines(self):
        nodes = {"A", "B", "C"}
        edges = [("A", "B"), ("B", "C")]
        self.assertEqual(critical_lines(nodes, edges), edges)


if __name__ == "__main__":
    unittest.main()

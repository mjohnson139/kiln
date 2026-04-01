from __future__ import annotations

import unittest

from kiln.dot import parse_dot


class ParseDotTests(unittest.TestCase):
    def test_parses_nodes_and_edges(self) -> None:
        workflow = parse_dot(
            """
            digraph sample {
              first [command="echo first"];
              second [command="echo second", cwd="."];
              first -> second;
            }
            """
        )
        self.assertEqual(set(workflow.nodes), {"first", "second"})
        self.assertEqual(workflow.nodes["second"].deps, ("first",))
        self.assertEqual(workflow.nodes["second"].cwd, ".")

    def test_parses_single_line_graph_body(self) -> None:
        workflow = parse_dot('digraph sample { first [command="echo first"]; }')
        self.assertEqual(set(workflow.nodes), {"first"})
        self.assertEqual(workflow.nodes["first"].command, "echo first")


if __name__ == "__main__":
    unittest.main()

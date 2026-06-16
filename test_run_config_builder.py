"""Unit tests for run configuration builder."""

from __future__ import annotations

import unittest
from pathlib import Path

from run_config_builder import (
    RunStackSnapshot,
    build_run_configuration,
    validate_run_configuration,
)


class RunConfigBuilderTests(unittest.TestCase):
    def _minimal_snapshot(self, *, selections: dict[str, set[str]] | None = None) -> RunStackSnapshot:
        return RunStackSnapshot(
            driver_path=Path("/tmp/driver.yaml"),
            driver_document={"experiment_config": {"agent_count": 4}},
            topologies_path=Path("/tmp/topologies.yaml"),
            topologies_document={"topologies": {"ring": {}, "star": {}, "mesh": {}}},
            assignments_path=Path("/tmp/assignments.yaml"),
            assignments_document={
                "profiles": {"p1": [{"agent": "all_agents", "profile": "prof_a"}]},
                "groupings": {"g1": [{"agent": "all_agents", "grouping": "grp_a"}]},
                "distributions": {"d1": [{"agent": "all_agents", "distribution": "dist_a"}]},
                "communications": {"c1": [{"agent": "all_agents", "communication": "comm_a"}]},
                "models": {"m1": [{"agent": "all_agents", "model": "model_a"}]},
            },
            definitions_path=Path("/tmp/definitions.yaml"),
            definitions_document={
                "agent_profiles": {"prof_a": {}},
                "groupings": {"grp_a": {}},
                "distributions": {"dist_a": {}},
                "communication_policies": {"comm_a": {}},
                "models": {"model_a": {}},
            },
            network_path=Path("/tmp/network.yaml"),
            network_document={"models": {"model_a": {}}},
            permutations_path=Path("/tmp/permutations.yaml"),
            permutations_document={},
            permutation_selections=selections
            or {
                "topology": {"ring", "star", "mesh"},
                "profile": {"p1", "p2"},
                "grouping": {"g1", "g2"},
                "distribution": {"d1", "d2"},
                "communication": {"c1"},
                "model": {"m1"},
            },
        )

    def test_estimated_run_count_is_cartesian_product(self) -> None:
        snapshot = self._minimal_snapshot()
        snapshot.assignments_document["profiles"]["p2"] = [
            {"agent": "all_agents", "profile": "prof_a"}
        ]
        snapshot.assignments_document["groupings"]["g2"] = [
            {"agent": "all_agents", "grouping": "grp_a"}
        ]
        snapshot.assignments_document["distributions"]["d2"] = [
            {"agent": "all_agents", "distribution": "dist_a"}
        ]
        config = build_run_configuration(snapshot)
        self.assertEqual(config.estimated_run_count, 3 * 2 * 2 * 2 * 1 * 1)
        self.assertEqual(len(config.combinations), config.estimated_run_count)

    def test_missing_topology_reports_validation_error(self) -> None:
        snapshot = self._minimal_snapshot(
            selections={
                "topology": {"missing_topo"},
                "profile": {"p1"},
                "grouping": {"g1"},
                "distribution": {"d1"},
                "communication": {"c1"},
                "model": {"m1"},
            }
        )
        config = build_run_configuration(snapshot)
        errors = validate_run_configuration(snapshot, config)
        self.assertTrue(any("missing_topo" in e for e in errors))

    def test_empty_selection_dimension_reports_error(self) -> None:
        snapshot = self._minimal_snapshot(
            selections={
                "topology": {"ring"},
                "profile": set(),
                "grouping": {"g1"},
                "distribution": {"d1"},
                "communication": {"c1"},
                "model": {"m1"},
            }
        )
        config = build_run_configuration(snapshot)
        errors = validate_run_configuration(snapshot, config)
        self.assertTrue(any("no profiles selected" in e.lower() for e in errors))
        self.assertEqual(config.estimated_run_count, 0)


if __name__ == "__main__":
    unittest.main()

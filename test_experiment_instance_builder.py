"""Unit tests for experiment instance builder."""

from __future__ import annotations

import unittest

from experiment_instance_builder import (
    build_experiment_instances,
    build_experiment_state_for_combination,
    format_instance_preview,
)
from run_config_builder import RunConfiguration


class ExperimentInstanceBuilderTests(unittest.TestCase):
    def _sample_run_config(self) -> RunConfiguration:
        return RunConfiguration(
            paths={"driver": "/tmp/driver.yaml"},
            selections={
                "topology": ["Complete", "ER"],
                "profile": ["HomoSync"],
                "grouping": ["g1"],
                "distribution": ["d1"],
                "communication": ["c1"],
                "model": ["m1"],
            },
            selection_counts={"topology": 2, "profile": 1, "grouping": 1, "distribution": 1, "communication": 1, "model": 1},
            combinations=[
                {
                    "topology": "Complete",
                    "profile": "HomoSync",
                    "grouping": "g1",
                    "distribution": "d1",
                    "communication": "c1",
                    "model": "m1",
                },
                {
                    "topology": "ER",
                    "profile": "HomoSync",
                    "grouping": "g1",
                    "distribution": "d1",
                    "communication": "c1",
                    "model": "m1",
                },
            ],
            estimated_run_count=2,
            driver={"experiment_config": {"seed": 42}, "paths": {"assignments": "/tmp/a.yaml"}},
            topologies={
                "topologies": {
                    "Complete": {"graph_type": "complete", "n": 8},
                    "ER": {"graph_type": "erdos_renyi", "n": 8, "p": 0.2},
                }
            },
            assignments={
                "assignments": {
                    "profile": {
                        "HomoSync": [{"agent": "all_agents", "profile": "prof_sync"}],
                    },
                    "grouping": {
                        "g1": [{"agent": "first_half", "grouping": "grp_a"}],
                    },
                    "data_distribution": {
                        "d1": [{"agent": "all_agents", "distribution": "dist_iid"}],
                    },
                    "communication_policy": {
                        "c1": [{"agent": "all_agents", "policy": "comm_low"}],
                    },
                    "model": {
                        "m1": [{"agent": "all_agents", "model": "cnn_def"}],
                    },
                }
            },
            definitions={
                "definitions": {
                    "agent_profiles": {
                        "prof_sync": {"role": "dfl_server", "is_sync": True, "aggregation": "average"},
                    },
                    "groupings": {"grp_a": {"round_start": 0, "round_end": 50}},
                    "data_distributions": {
                        "dist_iid": {
                            "training": {"dataset_start": 0, "dataset_end": 1000, "sampling": 500},
                            "validation": {"dataset_start": 0, "dataset_end": 200, "sampling": 100},
                        }
                    },
                    "communication_policies": {
                        "comm_low": {
                            "latency_probability": 0.1,
                            "drop_out_probability": 0.0,
                            "latency_minimum": 1,
                            "latency_maximum": 2,
                        }
                    },
                    "models": {
                        "cnn_def": {
                            "model_type": "CNN",
                            "batch_size": 32,
                            "optimizer": {"type": "SGD", "lr": 0.01},
                        }
                    },
                }
            },
            network={"models": {"cnn_def": {"type": "CNN"}}},
        )

    def test_builds_one_instance_per_combination(self) -> None:
        instances = build_experiment_instances(self._sample_run_config())
        self.assertEqual(len(instances), 2)
        self.assertEqual(instances[0].labels["topology"], "Complete")
        self.assertEqual(instances[1].labels["topology"], "ER")

    def test_resolves_topology_profile_and_communication(self) -> None:
        combo = self._sample_run_config().combinations[0]
        state = build_experiment_state_for_combination(self._sample_run_config(), combo, index=0)
        self.assertEqual(state["profiles"][0]["title"], "HomoSync")
        self.assertEqual(state["profiles"][0]["role"], "dfl_server")
        self.assertEqual(state["topology"]["graphs"][0]["graph_label"], "Complete")
        self.assertEqual(state["communication_cards"][0]["latency_prob"], "0.1")
        self.assertEqual(state["communication_cards"][0]["assignment_ranges"], [["", ""]])
        self.assertEqual(state["group_policy_cards"][0]["assignment"], [["", ""]])
        self.assertEqual(state["models"][0]["title"], "m1")
        self.assertEqual(state["environment"]["random_seed"], "42")

    def test_instance_preview_lists_dimensions(self) -> None:
        instances = build_experiment_instances(self._sample_run_config())
        preview = format_instance_preview(instances[0])
        self.assertIn("Topologies:", preview)
        self.assertIn("Complete", preview)
        self.assertIn("HomoSync", preview)


if __name__ == "__main__":
    unittest.main()

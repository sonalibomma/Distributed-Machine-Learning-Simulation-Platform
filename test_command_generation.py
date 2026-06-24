"""Tests for orchestrator command generation preview."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from command_generation import (
    build_orchestrator_command_from_manifests,
    build_orchestrator_command_from_requests,
    prepare_command_preview,
)
from manifest_export import MANIFEST_INDEX_FILENAME, export_instance_manifests
from orchestrator_adapter import OrchestratorAdapter
from run_config_builder import RunStackSnapshot, build_run_configuration
from test_orchestrator_adapter import _export_sample_manifests


class CommandGenerationTests(unittest.TestCase):
    def test_manifest_index_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=1)
            cmd = build_orchestrator_command_from_manifests(
                driver_path=Path("/tmp/driver.yaml"),
                export_dir=export_dir,
            )
            self.assertIn("python -m orchestrator", cmd)
            self.assertIn("--manifest-index", cmd)
            self.assertIn(MANIFEST_INDEX_FILENAME, cmd)
            self.assertIn("--export-dir", cmd)

    def test_instance_flag_when_single_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=1)
            adapter = OrchestratorAdapter(export_dir)
            result = adapter.load()
            cmd = build_orchestrator_command_from_requests(
                driver_path=Path("/tmp/driver.yaml"),
                export_dir=export_dir,
                execution_requests=result.execution_requests,
                active_instance_id=1,
            )
            self.assertIn("--instance", cmd)
            self.assertIn("experiment_instance_0001.yaml", cmd)

    def test_slurm_flag_for_remote_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=1)
            cmd = build_orchestrator_command_from_manifests(
                driver_path=Path("/tmp/driver.yaml"),
                export_dir=export_dir,
                mode="remote",
            )
            self.assertIn("--slurm", cmd)

    def test_prepare_command_preview_from_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = RunStackSnapshot(
                driver_path=Path("/tmp/driver.yaml"),
                driver_document={"experiment_config": {"seed": 1}, "paths": {}},
                topologies_path=Path("/tmp/topologies.yaml"),
                topologies_document={
                    "topologies": {
                        "Complete": {"graph_type": "complete", "n": 4},
                        "ER": {"graph_type": "erdos_renyi", "n": 4, "p": 0.2},
                    }
                },
                assignments_path=Path("/tmp/assignments.yaml"),
                assignments_document={
                    "assignments": {
                        "profile": {"HomoSync": [{"assignment": "all_agents", "profile": "prof_a"}]},
                        "grouping": {"g1": [{"assignment": "all_agents", "grouping": "grp_a"}]},
                        "data_distribution": {"d1": [{"assignment": "all_agents", "distribution": "dist_a"}]},
                        "communication_policy": {"c1": [{"assignment": "all_agents", "policy": "comm_a"}]},
                        "model": {"m1": [{"assignment": "all_agents", "model": "model_a"}]},
                    }
                },
                definitions_path=Path("/tmp/definitions.yaml"),
                definitions_document={
                    "definitions": {
                        "agent_profiles": {"prof_a": {"role": "dfl_server"}},
                        "groupings": {"grp_a": {"round_start": 0, "round_end": 10}},
                        "data_distributions": {
                            "dist_a": {"training": {"dataset_start": 0, "dataset_end": 100, "sampling": 50}}
                        },
                        "communication_policies": {"comm_a": {"latency_probability": 0.1}},
                        "models": {"model_a": {"model_type": "CNN"}},
                    }
                },
                network_path=Path("/tmp/network.yaml"),
                network_document={
                    "models": {
                        "model_a": {"type": "CNN", "layers": [{"type": "Conv2d", "params": {"in_channels": 1}}]}
                    }
                },
                permutations_path=Path("/tmp/permutations.yaml"),
                permutations_document={},
                permutation_selections={
                    "topology": {"Complete", "ER"},
                    "profile": {"HomoSync"},
                    "grouping": {"g1"},
                    "distribution": {"d1"},
                    "communication": {"c1"},
                    "model": {"m1"},
                },
            )

            preview = prepare_command_preview(snapshot, mode="local", staging_parent=Path(tmp))
            self.assertTrue(preview.valid, preview.errors)
            self.assertIn("python -m orchestrator", preview.command)
            self.assertEqual(preview.instance_count, 2)

    def test_prepare_command_preview_invalid_config(self) -> None:
        snapshot = RunStackSnapshot(
            driver_path=None,
            permutation_selections={},
        )
        preview = prepare_command_preview(snapshot)
        self.assertFalse(preview.valid)
        self.assertTrue(preview.errors)


if __name__ == "__main__":
    unittest.main()

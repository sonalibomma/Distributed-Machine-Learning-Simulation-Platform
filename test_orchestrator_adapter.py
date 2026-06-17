"""Tests for orchestrator adapter manifest loading and execution request generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiment_instance_builder import build_experiment_instances
from manifest_export import export_instance_manifests
from orchestrator_adapter import (
    ExecutionRequest,
    OrchestratorAdapter,
    build_execution_request,
    format_execution_preview,
    resolve_path,
    validate_instance_manifest_document,
    validate_manifest_version,
)
from run_config_builder import RunStackSnapshot, build_run_configuration


def _export_sample_manifests(export_dir: Path, *, topo_count: int = 2) -> None:
    snapshot = RunStackSnapshot(
        driver_path=Path("/tmp/driver.yaml"),
        driver_document={
            "experiment_config": {"seed": 1},
            "paths": {
                "driver": str(Path("/tmp/driver.yaml")),
                "topologies": str(Path("/tmp/topologies.yaml")),
            },
        },
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
            "models": {"model_a": {"type": "CNN", "layers": [{"type": "Conv2d", "params": {"in_channels": 1}}]}}
        },
        permutations_path=Path("/tmp/permutations.yaml"),
        permutations_document={},
        permutation_selections={
            "topology": {"Complete", "ER"} if topo_count > 1 else {"Complete"},
            "profile": {"HomoSync"},
            "grouping": {"g1"},
            "distribution": {"d1"},
            "communication": {"c1"},
            "model": {"m1"},
        },
    )
    if topo_count <= 1:
        snapshot.permutation_selections["topology"] = {"Complete"}
    config = build_run_configuration(snapshot)
    instances = build_experiment_instances(config)
    export_instance_manifests(instances, export_dir)


class OrchestratorAdapterTests(unittest.TestCase):
    def test_load_builds_execution_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=2)
            adapter = OrchestratorAdapter(export_dir, driver_root=Path("/tmp"))
            result = adapter.load()

            self.assertTrue(result.valid)
            self.assertEqual(result.instance_count, 2)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(result.manifest_version, 1)

            req = result.execution_requests[0]
            self.assertIsInstance(req, ExecutionRequest)
            self.assertEqual(req.instance_id, 1)
            self.assertTrue(req.manifest_path.is_file())
            self.assertIn("graphs", req.topology)
            self.assertIn("profile", req.assignments)

    def test_validate_manifest_version_rejects_unsupported(self) -> None:
        errors = validate_manifest_version(99)
        self.assertTrue(errors)
        self.assertTrue(any("not supported" in e for e in errors))

    def test_validate_instance_manifest_missing_fields(self) -> None:
        errors = validate_instance_manifest_document({"manifest_version": 1})
        self.assertTrue(any("instance_id" in e for e in errors))

    def test_resolve_path_relative_to_export_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            child = export_dir / "nested"
            child.mkdir()
            target = child / "driver.yaml"
            target.write_text("paths: {}\n", encoding="utf-8")

            resolved = resolve_path("nested/driver.yaml", export_dir=export_dir)
            self.assertEqual(resolved, target.resolve())

    def test_resolve_path_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            target = export_dir / "abs.yaml"
            target.write_text("x: 1\n", encoding="utf-8")
            resolved = resolve_path(str(target), export_dir=export_dir)
            self.assertEqual(resolved, target.resolve())

    def test_resolve_path_via_driver_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp) / "export"
            driver_root = Path(tmp) / "project"
            export_dir.mkdir()
            driver_root.mkdir()
            driver = driver_root / "driver.yaml"
            driver.write_text("experiment_config: {}\n", encoding="utf-8")

            resolved = resolve_path("driver.yaml", export_dir=export_dir, driver_root=driver_root)
            self.assertEqual(resolved, driver.resolve())

    def test_missing_index_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = OrchestratorAdapter(Path(tmp))
            result = adapter.load()
            self.assertFalse(result.valid)
            self.assertTrue(any("not found" in e.lower() for e in result.errors))

    def test_execution_preview_shows_validation_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=1)
            adapter = OrchestratorAdapter(export_dir)
            result = adapter.load()
            preview = format_execution_preview(result)
            self.assertIn("Execution Preview", preview)
            self.assertIn("Validation status: OK", preview)
            self.assertIn("Manifest version: 1", preview)
            self.assertIn("Instance count: 1", preview)

    def test_build_execution_request_from_loaded_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            _export_sample_manifests(export_dir, topo_count=1)
            adapter = OrchestratorAdapter(export_dir)
            result = adapter.load()
            req = result.execution_requests[0]
            payload = req.as_dict()
            self.assertEqual(payload["instance_id"], 1)
            self.assertIn("manifest_path", payload)
            self.assertIn("topology", payload)


if __name__ == "__main__":
    unittest.main()

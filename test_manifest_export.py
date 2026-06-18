from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiment_instance_builder import ExperimentInstance, build_experiment_instances
from experiment_io import read_yaml_file
from manifest_export import (
    MANIFEST_INDEX_FILENAME,
    build_instance_manifest,
    build_manifest_index,
    export_instance_manifests,
    instance_manifest_filename,
    load_instance_manifest,
    load_manifest_index,
    prepare_instances_for_export,
    validate_instances_for_export,
)
from run_config_builder import RunConfiguration, RunStackSnapshot, build_run_configuration


def _sample_snapshot() -> RunStackSnapshot:
    return RunStackSnapshot(
        driver_path=Path("/tmp/driver.yaml"),
        driver_document={"experiment_config": {"seed": 7}, "paths": {"permutations": "/tmp/permutations.yaml"}},
        topologies_path=Path("/tmp/topologies.yaml"),
        topologies_document={"topologies": {"Complete": {"graph_type": "complete", "n": 4}}},
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
        network_document={"models": {"model_a": {"type": "CNN", "layers": [{"type": "Conv2d", "params": {"in_channels": 1}}]}}},
        permutations_path=Path("/tmp/permutations.yaml"),
        permutations_document={},
        permutation_selections={
            "topology": {"Complete"},
            "profile": {"HomoSync"},
            "grouping": {"g1"},
            "distribution": {"d1"},
            "communication": {"c1"},
            "model": {"m1"},
        },
    )


class ManifestExportTests(unittest.TestCase):
    def test_instance_manifest_filename_numbering(self) -> None:
        self.assertEqual(instance_manifest_filename(1), "experiment_instance_0001.yaml")
        self.assertEqual(instance_manifest_filename(48), "experiment_instance_0048.yaml")

    def test_build_instance_manifest_contains_required_sections(self) -> None:
        snapshot = _sample_snapshot()
        config = build_run_configuration(snapshot)
        instances = build_experiment_instances(config)
        manifest = build_instance_manifest(instances[0], export_timestamp="2026-05-29T12:00:00+00:00")

        self.assertEqual(manifest["instance_id"], 1)
        self.assertEqual(manifest["manifest_version"], 1)
        self.assertIn("topology", manifest)
        self.assertIn("assignments", manifest)
        self.assertIn("definitions", manifest)
        self.assertIn("network", manifest)
        self.assertIn("metadata", manifest)
        self.assertIn("experiment_state", manifest)
        self.assertEqual(manifest["metadata"]["manifest_filename"], "experiment_instance_0001.yaml")
        self.assertEqual(manifest["labels"]["topology"], "Complete")

    def test_export_writes_files_and_index(self) -> None:
        snapshot = _sample_snapshot()
        config = build_run_configuration(snapshot)
        instances = build_experiment_instances(config)

        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            result = export_instance_manifests(
                instances,
                export_dir,
                export_timestamp="2026-05-29T12:00:00+00:00",
            )

            self.assertTrue(result.success)
            self.assertEqual(result.total_instances, 1)
            self.assertEqual(len(result.instance_files), 1)
            self.assertTrue(result.instance_files[0].is_file())
            self.assertTrue((export_dir / MANIFEST_INDEX_FILENAME).is_file())

            data = load_instance_manifest(result.instance_files[0])
            self.assertIsInstance(data, dict)
            self.assertEqual(data["instance_id"], 1)

            index = load_manifest_index(export_dir)
            self.assertEqual(index["total_instances"], 1)
            self.assertEqual(index["instance_files"], ["experiment_instance_0001.yaml"])
            self.assertEqual(index["instances"][0]["instance_id"], 1)

    def test_export_multiple_instances_correct_count(self) -> None:
        snapshot = _sample_snapshot()
        snapshot.topologies_document = {
            "topologies": {
                "Complete": {"graph_type": "complete", "n": 4},
                "ER": {"graph_type": "erdos_renyi", "n": 4, "p": 0.2},
            }
        }
        snapshot.permutation_selections["topology"] = {"Complete", "ER"}
        config = build_run_configuration(snapshot)
        instances = build_experiment_instances(config)

        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            result = export_instance_manifests(instances, export_dir)
            self.assertEqual(result.total_instances, 2)
            names = sorted(p.name for p in result.instance_files)
            self.assertEqual(
                names,
                ["experiment_instance_0001.yaml", "experiment_instance_0002.yaml"],
            )
            for path in result.instance_files:
                loaded = read_yaml_file(path)
                self.assertIsInstance(loaded, dict)
                self.assertIn("instance_id", loaded)

    def test_prepare_instances_for_export_validates(self) -> None:
        snapshot = _sample_snapshot()
        run_config, instances, errors = prepare_instances_for_export(snapshot)
        self.assertEqual(errors, [])
        self.assertIsNotNone(run_config)
        self.assertEqual(len(instances), 1)

    def test_validate_instances_for_export_empty_list(self) -> None:
        snapshot = _sample_snapshot()
        config = build_run_configuration(snapshot)
        errors = validate_instances_for_export(snapshot, config, [])
        self.assertTrue(any("no experiment instances" in e.lower() for e in errors))

    def test_manifest_index_structure(self) -> None:
        files = [
            Path("experiment_instance_0001.yaml"),
            Path("experiment_instance_0002.yaml"),
        ]
        index = build_manifest_index(files, export_timestamp="2026-05-29T12:00:00+00:00")
        self.assertEqual(index["total_instances"], 2)
        self.assertEqual(len(index["instances"]), 2)
        self.assertEqual(index["instances"][1]["instance_id"], 2)


if __name__ == "__main__":
    unittest.main()

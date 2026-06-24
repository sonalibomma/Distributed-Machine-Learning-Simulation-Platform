"""End-to-end workflow test using the demo YAML stack in yaml/."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from assignments_io import load_assignments_yaml, save_assignments_yaml, section_entries_from_document
from command_generation import prepare_command_preview
from definitions_io import load_definitions_yaml, save_definitions_yaml, section_entries_from_document
from driver_io import load_driver_yaml, resolve_driver_paths
from experiment_instance_builder import build_experiment_instances
from manifest_export import export_instance_manifests, load_instance_manifest, load_manifest_index
from orchestrator_adapter import OrchestratorAdapter
from permutations_io import load_permutations_yaml, save_permutations_yaml, selections_from_document
from run_config_builder import (
    RunStackSnapshot,
    build_and_validate_run_configuration,
    build_run_configuration,
    validate_run_configuration,
)
from topologies_io import load_topologies_yaml, save_topologies_yaml, topology_names
from network_io import load_network_yaml, save_network_yaml
from yaml_stack_sync import validate_yaml_stack


YAML_DIR = Path(__file__).resolve().parent / "yaml"


def _demo_snapshot(selections: dict[str, set[str]] | None = None) -> RunStackSnapshot:
    driver_path = YAML_DIR / "driver.yaml"
    driver = load_driver_yaml(driver_path)
    paths = resolve_driver_paths(driver, driver_file=driver_path)

    topo_path = paths.get("topologies") or YAML_DIR / "topologies.yaml"
    assign_path = paths.get("assignments") or YAML_DIR / "assignments.yaml"
    defn_path = paths.get("definitions") or YAML_DIR / "definitions.yaml"
    perm_path = paths.get("permutations") or YAML_DIR / "permutations.yaml"
    net_path = paths.get("network") or YAML_DIR / "network.yaml"

    perm_doc = load_permutations_yaml(perm_path)
    perm_selections = selections if selections is not None else {
        key: set(vals) for key, vals in selections_from_document(perm_doc).items()
    }

    return RunStackSnapshot(
        driver_path=driver_path,
        driver_document=driver,
        topologies_path=topo_path,
        topologies_document=load_topologies_yaml(topo_path),
        assignments_path=assign_path,
        assignments_document=load_assignments_yaml(assign_path),
        definitions_path=defn_path,
        definitions_document=load_definitions_yaml(defn_path),
        network_path=net_path,
        network_document=load_network_yaml(net_path),
        permutations_path=perm_path,
        permutations_document=perm_doc,
        permutation_selections=perm_selections,
    )


class EndToEndWorkflowTests(unittest.TestCase):
    def test_demo_yaml_stack_paths_resolve(self) -> None:
        driver_path = YAML_DIR / "driver.yaml"
        driver = load_driver_yaml(driver_path)
        paths = resolve_driver_paths(driver, driver_file=driver_path)
        for key in ("definitions", "topologies", "assignments", "permutations", "network"):
            path = paths.get(key)
            self.assertIsNotNone(path, f"Missing resolved path for {key}")
            self.assertTrue(path.is_file(), f"Demo file not found for {key}: {path}")

    def test_cross_page_validation_passes(self) -> None:
        snapshot = _demo_snapshot()
        errors = validate_yaml_stack(snapshot)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_run_configuration_and_instances(self) -> None:
        snapshot = _demo_snapshot()
        config, errors = build_and_validate_run_configuration(snapshot)
        self.assertEqual(errors, [], "\n".join(errors))
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.estimated_run_count, 4)  # 2 topologies x 2 profiles x 1 each other
        instances = build_experiment_instances(config)
        self.assertEqual(len(instances), 4)

    def test_manifest_export_and_adapter(self) -> None:
        snapshot = _demo_snapshot()
        config = build_run_configuration(snapshot)
        instances = build_experiment_instances(config)
        with tempfile.TemporaryDirectory() as tmp:
            export_dir = Path(tmp)
            result = export_instance_manifests(instances, export_dir)
            self.assertTrue(result.success)
            index = load_manifest_index(export_dir)
            self.assertEqual(index["total_instances"], 4)
            adapter = OrchestratorAdapter(export_dir, driver_root=YAML_DIR)
            loaded = adapter.load()
            self.assertTrue(loaded.valid, "\n".join(loaded.errors))
            self.assertEqual(loaded.instance_count, 4)
            manifest = load_instance_manifest(loaded.manifest_paths[0])
            self.assertEqual(manifest["manifest_version"], 1)

    def test_command_preview_generation(self) -> None:
        snapshot = _demo_snapshot()
        preview = prepare_command_preview(snapshot, staging_parent=YAML_DIR)
        self.assertTrue(preview.valid, "\n".join(preview.errors))
        self.assertIn("python -m orchestrator", preview.command)
        self.assertIn("manifest_index.yaml", preview.command)

    def test_save_reload_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            driver_path = YAML_DIR / "driver.yaml"
            driver = load_driver_yaml(driver_path)
            paths = resolve_driver_paths(driver, driver_file=driver_path)

            topo_path = tmp_path / "topologies.yaml"
            assign_path = tmp_path / "assignments.yaml"
            defn_path = tmp_path / "definitions.yaml"
            perm_path = tmp_path / "permutations.yaml"
            net_path = tmp_path / "network.yaml"

            topo_doc = load_topologies_yaml(paths["topologies"])
            assign_doc = load_assignments_yaml(paths["assignments"])
            defn_doc = load_definitions_yaml(paths["definitions"])
            perm_doc = load_permutations_yaml(paths["permutations"])
            net_doc = load_network_yaml(paths["network"])

            save_topologies_yaml(topo_path, topo_doc)
            save_assignments_yaml(assign_path, assign_doc)
            save_definitions_yaml(defn_path, defn_doc)
            save_permutations_yaml(perm_path, perm_doc)
            save_network_yaml(net_path, net_doc)

            self.assertEqual(
                topology_names(load_topologies_yaml(topo_path)),
                topology_names(topo_doc),
            )
            self.assertEqual(
                section_entries_from_document(load_assignments_yaml(assign_path)),
                section_entries_from_document(assign_doc),
            )
            self.assertEqual(
                section_entries_from_document(load_definitions_yaml(defn_path)),
                section_entries_from_document(defn_doc),
            )
            self.assertEqual(
                selections_from_document(load_permutations_yaml(perm_path)),
                selections_from_document(perm_doc),
            )

    def test_invalid_reference_surfaces_clear_error(self) -> None:
        snapshot = _demo_snapshot()
        snapshot.permutation_selections["topology"] = {"MissingTopology"}
        config = build_run_configuration(snapshot)
        errors = validate_run_configuration(snapshot, config)
        self.assertTrue(any("MissingTopology" in e for e in errors))


if __name__ == "__main__":
    unittest.main()

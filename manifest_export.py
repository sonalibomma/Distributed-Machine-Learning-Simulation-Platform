"""Serialize ExperimentInstance objects to YAML manifest files for orchestrator handoff."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_instance_builder import ExperimentInstance
from experiment_io import read_yaml_file, write_yaml_file
from run_config_builder import (
    PERMUTATION_DIMENSIONS,
    RunConfiguration,
    RunStackSnapshot,
    build_and_validate_run_configuration,
    validate_run_configuration,
)

MANIFEST_VERSION = 1
INSTANCE_MANIFEST_PREFIX = "experiment_instance_"
INSTANCE_MANIFEST_SUFFIX = ".yaml"
MANIFEST_INDEX_FILENAME = "manifest_index.yaml"


@dataclass
class ManifestExportResult:
    """Outcome of writing instance manifests to disk."""

    export_dir: Path
    instance_files: list[Path] = field(default_factory=list)
    index_file: Path | None = None
    total_instances: int = 0
    export_timestamp: str = ""

    @property
    def success(self) -> bool:
        return self.total_instances > 0 and len(self.instance_files) == self.total_instances


def instance_manifest_filename(instance_number: int) -> str:
    """Deterministic manifest filename for a 1-based instance number."""
    return f"{INSTANCE_MANIFEST_PREFIX}{int(instance_number):04d}{INSTANCE_MANIFEST_SUFFIX}"


def utc_export_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _definition_refs_from_state(experiment_state: dict[str, Any]) -> dict[str, str]:
    """Best-effort definition references extracted from resolved experiment state."""
    refs: dict[str, str] = {}
    profiles = experiment_state.get("profiles")
    if isinstance(profiles, list) and profiles and isinstance(profiles[0], dict):
        desc = str(profiles[0].get("description", ""))
        for line in desc.splitlines():
            if line.startswith("Definition:"):
                refs["profile"] = line.split(":", 1)[1].strip()
                break
    models = experiment_state.get("models")
    if isinstance(models, list) and models and isinstance(models[0], dict):
        desc = str(models[0].get("description", ""))
        for line in desc.splitlines():
            if line.startswith("Definition:"):
                refs["model"] = line.split(":", 1)[1].strip()
                break
    return refs


def build_instance_manifest(
    instance: ExperimentInstance,
    *,
    export_timestamp: str | None = None,
) -> dict[str, Any]:
    """
    Build a manifest document for one experiment instance.

    ``ExperimentInstance.as_dict()`` is the canonical core; this adds structured
    sections for topology, assignments, definitions, network, and metadata.
    """
    canonical = instance.as_dict()
    state = canonical.get("experiment_state") if isinstance(canonical.get("experiment_state"), dict) else {}
    ts = export_timestamp or utc_export_timestamp()
    filename = instance_manifest_filename(instance.instance_number)

    combination = canonical.get("combination") if isinstance(canonical.get("combination"), dict) else {}
    labels = canonical.get("labels") if isinstance(canonical.get("labels"), dict) else {}

    return {
        "manifest_version": MANIFEST_VERSION,
        "instance_id": canonical.get("instance_number", instance.instance_number),
        "instance_index": canonical.get("index", instance.index),
        "combination": combination,
        "labels": labels,
        "topology": state.get("topology", {}),
        "assignments": {
            key: str(combination.get(key, ""))
            for key, _label in PERMUTATION_DIMENSIONS
            if key != "topology"
        },
        "definitions": _definition_refs_from_state(state),
        "network": state.get("network_config", {}),
        "paths": canonical.get("paths", {}),
        "metadata": {
            "export_timestamp": ts,
            "manifest_filename": filename,
            "display_label": instance.display_label(),
        },
        "experiment_state": state,
    }


def build_manifest_index(
    instance_files: list[Path],
    *,
    export_timestamp: str | None = None,
) -> dict[str, Any]:
    """Build manifest_index.yaml payload."""
    ts = export_timestamp or utc_export_timestamp()
    entries: list[dict[str, Any]] = []
    for path in instance_files:
        stem = path.name
        # instance_id from filename experiment_instance_0001.yaml
        try:
            num_part = stem.replace(INSTANCE_MANIFEST_PREFIX, "").replace(INSTANCE_MANIFEST_SUFFIX, "")
            instance_id = int(num_part)
        except ValueError:
            instance_id = len(entries) + 1
        entries.append({"instance_id": instance_id, "filename": path.name})

    return {
        "manifest_version": MANIFEST_VERSION,
        "total_instances": len(instance_files),
        "export_timestamp": ts,
        "instance_files": [p.name for p in instance_files],
        "instances": entries,
    }


def format_manifest_preview(instance: ExperimentInstance) -> str:
    """Preview text for the Instance Manifest Preview panel."""
    manifest = build_instance_manifest(instance)
    lines = [
        "Instance Manifest Preview",
        "",
        f"Instance ID: {manifest.get('instance_id')}",
        f"Manifest file: {manifest['metadata']['manifest_filename']}",
        "",
    ]
    preview_keys = (
        ("topology", "Topology"),
        ("profile", "Profile"),
        ("grouping", "Grouping"),
        ("distribution", "Distribution"),
        ("communication", "Communication"),
        ("model", "Model"),
    )
    labels = manifest.get("labels") if isinstance(manifest.get("labels"), dict) else {}
    combination = manifest.get("combination") if isinstance(manifest.get("combination"), dict) else {}
    for key, label in preview_keys:
        if key == "topology":
            value = labels.get("topology") or combination.get("topology", "")
        else:
            value = labels.get(key) or combination.get(key, "")
        lines.append(f"{label}: {value or '(none)'}")
    defs = manifest.get("definitions")
    if isinstance(defs, dict) and defs:
        lines.append("")
        lines.append("Definition refs:")
        for k, v in defs.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines).strip()


def validate_instances_for_export(
    snapshot: RunStackSnapshot,
    run_config: RunConfiguration,
    instances: list[ExperimentInstance],
) -> list[str]:
    """Validate run configuration and instance list before manifest export."""
    errors = list(validate_run_configuration(snapshot, run_config))
    if not instances:
        errors.append("Manifest export: no experiment instances to export.")
    expected = run_config.estimated_run_count
    if expected > 0 and len(instances) != expected:
        errors.append(
            f"Manifest export: expected {expected} instance(s) but built {len(instances)}."
        )
    return errors


def prepare_instances_for_export(
    snapshot: RunStackSnapshot,
) -> tuple[RunConfiguration | None, list[ExperimentInstance], list[str]]:
    """Build and validate run configuration + instances for export."""
    from experiment_instance_builder import build_experiment_instances

    run_config, errors = build_and_validate_run_configuration(snapshot)
    if errors or run_config is None:
        return None, [], errors
    instances = build_experiment_instances(run_config)
    errors = validate_instances_for_export(snapshot, run_config, instances)
    if errors:
        return run_config, instances, errors
    return run_config, instances, []


def export_instance_manifests(
    instances: list[ExperimentInstance],
    export_dir: Path,
    *,
    export_timestamp: str | None = None,
    write_index: bool = True,
) -> ManifestExportResult:
    """Write one YAML manifest per instance and optional manifest_index.yaml."""
    export_dir = export_dir.resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = export_timestamp or utc_export_timestamp()

    instance_files: list[Path] = []
    for instance in instances:
        manifest = build_instance_manifest(instance, export_timestamp=ts)
        filename = instance_manifest_filename(instance.instance_number)
        path = export_dir / filename
        write_yaml_file(path, manifest)
        instance_files.append(path)

    index_file: Path | None = None
    if write_index and instance_files:
        index_file = export_dir / MANIFEST_INDEX_FILENAME
        write_yaml_file(index_file, build_manifest_index(instance_files, export_timestamp=ts))

    return ManifestExportResult(
        export_dir=export_dir,
        instance_files=instance_files,
        index_file=index_file,
        total_instances=len(instance_files),
        export_timestamp=ts,
    )


def load_manifest_index(export_dir: Path) -> dict[str, Any]:
    path = export_dir / MANIFEST_INDEX_FILENAME
    data = read_yaml_file(path)
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST_INDEX_FILENAME} must contain a YAML mapping.")
    return data


def load_instance_manifest(path: Path) -> dict[str, Any]:
    data = read_yaml_file(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping.")
    return data

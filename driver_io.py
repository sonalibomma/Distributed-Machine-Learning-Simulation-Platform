"""Load, validate, and save driver.yaml for the simulation platform."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from experiment_io import read_yaml_file, write_yaml_file

DRIVER_FILENAME = "driver.yaml"

# GUI field keys (flat) mapped to nested document paths.
_FIELD_PATHS: dict[str, tuple[str, ...]] = {
    "slurm_partition": ("slurm", "partition"),
    "slurm_gres": ("slurm", "gres"),
    "slurm_cpus_per_task": ("slurm", "cpus-per-task"),
    "slurm_mem": ("slurm", "mem"),
    "slurm_time": ("slurm", "time"),
    "experiment_communication_rounds": ("experiment_config", "communication_rounds"),
    "experiment_seed": ("experiment_config", "seed"),
    "experiment_save_raw_data_as_mat": ("experiment_config", "save_raw_data_as_mat"),
    "experiment_agent_count": ("experiment_config", "agent_count"),
    "paths_definitions": ("paths", "definitions"),
    "paths_assignments": ("paths", "assignments"),
    "paths_topologies": ("paths", "topologies"),
    "paths_permutations": ("paths", "permutations"),
    "paths_network": ("paths", "network"),
    "paths_save": ("paths", "save_path"),
    "environment_virtualenv": ("paths", "venv_activate"),
    "environment_requirements": ("paths", "requirements_file"),
    "environment_modules": ("slurm_setup", "modules"),
}

# Read paths tried in order (first present value wins). Includes backend driver.yaml layouts.
_READ_PATHS: dict[str, list[tuple[str, ...]]] = {
    "slurm_partition": [("slurm", "partition"), ("partition",)],
    "slurm_gres": [("slurm", "gres"), ("gres",)],
    "slurm_cpus_per_task": [("slurm", "cpus-per-task"), ("slurm", "cpus_per_task"), ("cpus-per-task",), ("cpus_per_task",)],
    "slurm_mem": [("slurm", "mem"), ("mem",)],
    "slurm_time": [("slurm", "time"), ("time",)],
    "experiment_communication_rounds": [
        ("experiment_config", "communication_rounds"),
    ],
    "experiment_seed": [
        ("experiment_config", "seed"),
    ],
    "experiment_save_raw_data_as_mat": [
        ("experiment_config", "save_raw_data_as_mat"),
    ],
    "experiment_agent_count": [
        ("experiment_config", "agent_count"),
    ],
    "paths_definitions": [
        ("paths", "definitions"),
        ("definitions",),
        ("dir_path", "definitions"),
    ],
    "paths_assignments": [
        ("paths", "assignments"),
        ("assignments",),
        ("dir_path", "assignments"),
        ("dir_path", "agent_assignment"),
    ],
    "paths_topologies": [
        ("paths", "topologies"),
        ("topologies",),
        ("dir_path", "topologies"),
        ("dir_path", "topology"),
    ],
    "paths_permutations": [
        ("paths", "permutations"),
        ("permutations",),
        ("dir_path", "permutations"),
    ],
    "paths_network": [
        ("paths", "network"),
        ("network",),
        ("dir_path", "network"),
    ],
    "paths_save": [
        ("paths", "save_path"),
    ],
    "environment_virtualenv": [
        ("paths", "venv_activate"),
        ("slurm_setup", "venv_activate"),
    ],
    "environment_requirements": [
        ("paths", "requirements_file"),
    ],
    "environment_modules": [
        ("slurm_setup", "modules"),
    ],
}


def default_driver_document() -> dict[str, Any]:
    return {
        "slurm": {
            "partition": "",
            "gres": "",
            "cpus-per-task": "",
            "mem": "",
            "time": "",
        },
        "experiment_config": {
            "communication_rounds": "",
            "seed": "",
            "save_raw_data_as_mat": False,
            "agent_count": "",
        },
        "paths": {
            "save_path": "",
            "venv_activate": "",
            "requirements_file": "",
            "definitions": "",
            "assignments": "",
            "topologies": "",
            "permutations": "",
            "network": "",
        },
        "slurm_setup": {
            "venv_activate": "",
            "modules": [],
        },
    }


def _dig(data: Any, path: tuple[str, ...]) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _ensure_path(doc: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    cur: dict[str, Any] = doc
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    return cur


def _value_present(val: Any) -> bool:
    """True if val is a usable field value (0 and False are valid)."""
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def _yaml_path_str(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _pick_field_with_path(raw: dict[str, Any], gui_key: str) -> tuple[tuple[str, ...] | None, Any]:
    """Return (yaml_path, value) for the first matching location."""
    paths = _READ_PATHS.get(gui_key, [_FIELD_PATHS[gui_key]])
    for path in paths:
        val = _dig(raw, path)
        if isinstance(val, bool) or _value_present(val):
            return path, val
    return None, None


def _pick_field(raw: dict[str, Any], gui_key: str) -> Any:
    _path, val = _pick_field_with_path(raw, gui_key)
    return val


def path_and_environment_field_mappings(doc: dict[str, Any]) -> dict[str, str]:
    """Resolved YAML paths for paths/environment GUI fields."""
    labels = {
        "paths_save": "Save Path",
        "environment_virtualenv": "Virtual Environment",
        "environment_requirements": "Requirements File",
        "environment_modules": "Modules",
    }
    out: dict[str, str] = {}
    for key, label in labels.items():
        path, _val = _pick_field_with_path(doc, key)
        out[label] = _yaml_path_str(path) if path else "(not found)"
    return out


def experiment_field_mappings(doc: dict[str, Any]) -> dict[str, str]:
    """Resolved YAML paths for experiment-configuration GUI fields."""
    labels = {
        "experiment_communication_rounds": "Communication Rounds",
        "experiment_seed": "Seed",
        "experiment_save_raw_data_as_mat": "Save raw data as MAT",
        "experiment_agent_count": "Agent count",
    }
    out: dict[str, str] = {}
    for key, label in labels.items():
        path, _val = _pick_field_with_path(doc, key)
        out[label] = _yaml_path_str(path) if path else "(not found)"
    return out


def print_driver_load_report(doc: dict[str, Any], *, source: Path | str | None = None) -> None:
    """Print discovered YAML hierarchy and field mappings to the console."""
    src = f" ({source})" if source else ""
    print(f"\n=== Driver YAML structure{src} ===")
    for section in ("paths", "slurm", "slurm_setup", "experiment_config"):
        block = doc.get(section)
        if isinstance(block, dict):
            print(f"{section}:")
            for k, v in block.items():
                if isinstance(v, list):
                    print(f"  {k}: [{len(v)} item(s)]")
                elif isinstance(v, dict):
                    print(f"  {k}: {{...}}")
                else:
                    print(f"  {k}: {v!r}")
    print("\n=== Experiment field mappings ===")
    for label, yaml_path in experiment_field_mappings(doc).items():
        print(f"  {label} → {yaml_path}")
    print("\n=== Paths / environment field mappings ===")
    for label, yaml_path in path_and_environment_field_mappings(doc).items():
        print(f"  {label} → {yaml_path}")
    vals = gui_values_from_document(doc)
    print("\n=== Populated GUI values ===")
    for label, key in (
        ("Communication Rounds", "experiment_communication_rounds"),
        ("Seed", "experiment_seed"),
        ("Save raw data as MAT", "experiment_save_raw_data_as_mat"),
        ("Agent count", "experiment_agent_count"),
        ("Save Path", "paths_save"),
        ("Virtual Environment", "environment_virtualenv"),
        ("Requirements File", "environment_requirements"),
        ("Modules", "environment_modules"),
    ):
        print(f"  {label}: {vals.get(key)!r}")
    print()


def gui_values_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Extract flat GUI values from a loaded driver.yaml document."""
    raw = doc if isinstance(doc, dict) else {}
    modules_val = _pick_field(raw, "environment_modules")
    if isinstance(modules_val, list):
        modules_text = "\n".join(str(x) for x in modules_val)
    elif modules_val is None:
        modules_text = ""
    else:
        modules_text = str(modules_val)

    save_mat = _pick_field(raw, "experiment_save_raw_data_as_mat")
    if save_mat is None:
        save_mat_bool = False
    elif isinstance(save_mat, bool):
        save_mat_bool = save_mat
    else:
        save_mat_bool = str(save_mat).strip().lower() in ("1", "true", "yes", "on")

    def _s(key: str) -> str:
        v = _pick_field(raw, key)
        return "" if v is None else str(v)

    return {
        "slurm_partition": _s("slurm_partition"),
        "slurm_gres": _s("slurm_gres"),
        "slurm_cpus_per_task": _s("slurm_cpus_per_task"),
        "slurm_mem": _s("slurm_mem"),
        "slurm_time": _s("slurm_time"),
        "experiment_communication_rounds": _s("experiment_communication_rounds"),
        "experiment_seed": _s("experiment_seed"),
        "experiment_save_raw_data_as_mat": save_mat_bool,
        "experiment_agent_count": _s("experiment_agent_count"),
        "paths_definitions": _s("paths_definitions"),
        "paths_assignments": _s("paths_assignments"),
        "paths_topologies": _s("paths_topologies"),
        "paths_permutations": _s("paths_permutations"),
        "paths_network": _s("paths_network"),
        "paths_save": _s("paths_save"),
        "environment_virtualenv": _s("environment_virtualenv"),
        "environment_requirements": _s("environment_requirements"),
        "environment_modules": modules_text,
    }


def merge_gui_into_document(base: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Merge GUI values into a document, preserving unknown keys from the loaded file."""
    out = copy.deepcopy(base) if isinstance(base, dict) else default_driver_document()

    def _set(gui_key: str, value: Any) -> None:
        path = _FIELD_PATHS[gui_key]
        parent = _ensure_path(out, path)
        parent[path[-1]] = value

    _set("slurm_partition", values.get("slurm_partition", ""))
    _set("slurm_gres", values.get("slurm_gres", ""))
    _set("slurm_cpus_per_task", values.get("slurm_cpus_per_task", ""))
    _set("slurm_mem", values.get("slurm_mem", ""))
    _set("slurm_time", values.get("slurm_time", ""))
    _set("experiment_communication_rounds", values.get("experiment_communication_rounds", ""))
    _set("experiment_seed", values.get("experiment_seed", ""))
    _set("experiment_save_raw_data_as_mat", bool(values.get("experiment_save_raw_data_as_mat", False)))

    for key in (
        "experiment_agent_count",
        "paths_definitions",
        "paths_assignments",
        "paths_topologies",
        "paths_permutations",
        "paths_network",
        "paths_save",
        "environment_virtualenv",
        "environment_requirements",
    ):
        _set(key, values.get(key, ""))

    modules_text = str(values.get("environment_modules", "") or "").strip()
    modules_list = [ln.strip() for ln in modules_text.splitlines() if ln.strip()]
    _set("environment_modules", modules_list)

    # Keep slurm_setup.venv_activate in sync when present in the loaded document.
    venv = values.get("environment_virtualenv", "")
    if isinstance(out.get("slurm_setup"), dict):
        out["slurm_setup"]["venv_activate"] = venv

    return out


def _parse_int_field(value: str, label: str) -> tuple[int | None, str | None]:
    s = str(value).strip()
    if not s:
        return None, None
    try:
        v = int(s)
    except ValueError:
        return None, f"{label} must be an integer."
    return v, None


def validate_driver_values(values: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    cpus = str(values.get("slurm_cpus_per_task", "")).strip()
    if cpus:
        try:
            if int(cpus) <= 0:
                errors.append("cpus-per-task must be a positive integer.")
        except ValueError:
            errors.append("cpus-per-task must be a positive integer.")

    mem = str(values.get("slurm_mem", "")).strip()
    if mem and not re.match(r"^\d+(\.\d+)?[KMGTP]?B?$", mem, re.I) and not mem.isdigit():
        errors.append("mem should look like a Slurm memory value (e.g. 16G or 16384).")

    time_val = str(values.get("slurm_time", "")).strip()
    if time_val and not re.match(r"^\d+([:-]\d{2}){0,2}$", time_val):
        errors.append("time should look like a Slurm time limit (e.g. 01:00:00 or 60).")

    for label, key in (
        ("communication_rounds", "experiment_communication_rounds"),
        ("seed", "experiment_seed"),
        ("agent_count", "experiment_agent_count"),
    ):
        _, err = _parse_int_field(str(values.get(key, "")), label)
        if err:
            errors.append(err)
        else:
            raw = str(values.get(key, "")).strip()
            if raw:
                try:
                    if int(raw) < 0 and key != "experiment_seed":
                        errors.append(f"{label} must be >= 0.")
                except ValueError:
                    pass

    return (len(errors) == 0, errors)


def load_driver_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_driver_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")
    # Merge onto defaults so all sections exist for round-trip save.
    merged = default_driver_document()
    for section, content in raw.items():
        if isinstance(content, dict) and section in merged and isinstance(merged[section], dict):
            merged[section].update(content)
        else:
            merged[section] = copy.deepcopy(content)
    # Promote known backend top-level scalars into canonical nested sections for save round-trip.
    gui = gui_values_from_document(merged)
    merged = merge_gui_into_document(merged, gui)
    merged["_source_keys"] = list(raw.keys())
    merged["_source_path"] = str(path.resolve())
    return merged


def save_driver_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_keys", None)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def resolve_driver_paths(
    document: dict[str, Any],
    *,
    driver_file: Path | str | None = None,
) -> dict[str, Path | None]:
    """
    Resolve all YAML stack paths referenced by driver.yaml.

    Returns mapping keys: definitions, assignments, topologies, permutations, network.
    """
    from assignments_io import resolve_assignments_path
    from definitions_io import resolve_definitions_path
    from network_io import resolve_network_path
    from permutations_io import resolve_permutations_path
    from topologies_io import resolve_topologies_path

    vals = gui_values_from_document(document)
    driver = Path(driver_file).resolve() if driver_file else None

    return {
        "definitions": resolve_definitions_path(str(vals.get("paths_definitions", "") or ""), driver_file=driver),
        "assignments": resolve_assignments_path(str(vals.get("paths_assignments", "") or ""), driver_file=driver),
        "topologies": resolve_topologies_path(str(vals.get("paths_topologies", "") or ""), driver_file=driver),
        "permutations": resolve_permutations_path(str(vals.get("paths_permutations", "") or ""), driver_file=driver),
        "network": resolve_network_path(str(vals.get("paths_network", "") or ""), driver_file=driver),
    }


def format_missing_driver_paths(paths: dict[str, Path | None]) -> list[str]:
    """User-friendly errors for YAML files referenced by driver.yaml that were not found."""
    labels = {
        "definitions": "definitions.yaml (paths.definitions)",
        "assignments": "assignments.yaml (paths.assignments)",
        "topologies": "topologies.yaml (paths.topologies)",
        "permutations": "permutations.yaml (paths.permutations)",
        "network": "network.yaml (paths.network)",
    }
    errors: list[str] = []
    for key, label in labels.items():
        if paths.get(key) is None:
            errors.append(f"Driver: could not find {label}. Check paths in driver.yaml.")
    return errors

"""Read-only synchronization and validation between the Driver YAML stack and the Experiment tab."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assignments_io import (
    section_entries_from_document as assignment_entries_from_document,
    validate_sections as validate_assignment_sections,
    reference_names_from_definitions,
)
from definitions_io import (
    section_entries_from_document as definition_entries_from_document,
    validate_sections as validate_definition_sections,
)
from driver_io import gui_values_from_document, validate_driver_values
from experiment_data import (
    default_model_state,
    default_profile_state,
    default_topology_graph_block,
    normalize_topology_graph_block,
)
from network_io import gui_state_from_document as network_gui_state_from_document, validate_network_state
from topologies_io import (
    topology_block,
    topology_names,
    validate_topologies_collection,
    canonical_from_yaml_graph_type,
)


@dataclass
class YamlStackSnapshot:
    """Loaded YAML documents and paths from the Driver configuration stack."""

    driver_path: Path | None = None
    driver_document: dict[str, Any] | None = None
    topologies_path: Path | None = None
    topologies_document: dict[str, Any] | None = None
    assignments_path: Path | None = None
    assignments_document: dict[str, Any] | None = None
    definitions_path: Path | None = None
    definitions_document: dict[str, Any] | None = None
    network_path: Path | None = None
    network_document: dict[str, Any] | None = None


def _source_label(path: Path | None, fallback: str) -> str:
    if path is not None:
        return f"Source: {path.name}"
    return f"Source: {fallback} (not loaded)"


def _topology_preview(topologies_document: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(topologies_document, dict):
        return {"graphs": [default_topology_graph_block()], "active_graph_index": 0, **default_topology_graph_block()}

    names = topology_names(topologies_document)
    if not names:
        base = default_topology_graph_block()
        return {"graphs": [base], "active_graph_index": 0, **base}

    graphs: list[dict[str, Any]] = []
    for name in names:
        block = topology_block(topologies_document, name)
        gt = canonical_from_yaml_graph_type(block.get("graph_type"))
        merged = {**block, "graph_type": gt}
        g = normalize_topology_graph_block(merged)
        g["graph_label"] = name
        g["validation_text"] = f"Validation: synced from topologies.yaml ({name})"
        graphs.append(g)

    active = graphs[0]
    return {
        "graphs": graphs,
        "active_graph_index": 0,
        **active,
    }


def _profile_rows_to_description(assign_name: str, rows: list[tuple[str, str]]) -> str:
    lines = [f"Assignment: {assign_name}"]
    for agent, ref in rows:
        a, r = str(agent).strip(), str(ref).strip()
        if a or r:
            lines.append(f"  {a or '?'} → {r or '?'}")
    return "\n".join(lines)


def _definition_to_profile_gui(
    defn_name: str,
    block: dict[str, Any],
    assign_name: str,
    rows: list[tuple[str, str]],
) -> dict[str, Any]:
    p = default_profile_state(1)
    p["title"] = assign_name or defn_name
    p["description"] = _profile_rows_to_description(assign_name, rows)
    if defn_name:
        p["description"] = f"Definition: {defn_name}\n" + p["description"]

    if block.get("role") is not None:
        p["role"] = str(block["role"])
    if block.get("aggregation") is not None:
        p["aggregation"] = str(block["aggregation"])
    for key, dst in (
        ("wait_time", "wait_time"),
        ("aggregation_minimum", "agg_min"),
        ("freshness_cap", "freshness_cap"),
        ("training_time", "training_time"),
        ("neighbor_ratio", "neighbor_ratio"),
        ("epochs", "epochs"),
        ("release_agent", "release_agent"),
    ):
        if block.get(key) is not None:
            p[dst] = str(block[key])
    mb = block.get("mini_batches", block.get("minibatches"))
    if mb is not None:
        p["minibatches"] = str(mb)
    metrics = block.get("metrics")
    if isinstance(metrics, list):
        p["metrics"] = ", ".join(str(m) for m in metrics)
    elif metrics is not None:
        p["metrics"] = str(metrics)
    if "does_train" in block:
        p["does_train"] = bool(block["does_train"])
    if "is_sync" in block:
        p["is_sync"] = bool(block["is_sync"])
    if "checkpoint_enabled" in block:
        p["checkpoint"] = bool(block["checkpoint_enabled"])
    return p


def _profiles_preview(
    assignments_document: dict[str, Any] | None,
    definitions_document: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(assignments_document, dict):
        return [default_profile_state(1)]

    defn_map = {
        name: block
        for name, block in definition_entries_from_document(definitions_document or {}).get("agent_profiles", [])
    }
    assign_entries = assignment_entries_from_document(assignments_document).get("profile", [])
    if not assign_entries:
        if defn_map:
            return [_definition_to_profile_gui(name, block, name, []) for name, block in defn_map.items()]
        return [default_profile_state(1)]

    profiles: list[dict[str, Any]] = []
    for assign_name, rows in assign_entries:
        primary_ref = next((str(r).strip() for _a, r in rows if str(r).strip()), "")
        block = defn_map.get(primary_ref, {})
        profiles.append(_definition_to_profile_gui(primary_ref, block, assign_name, rows))
    return profiles or [default_profile_state(1)]


def _definition_to_model_gui(
    defn_name: str,
    block: dict[str, Any],
    assign_name: str,
    rows: list[tuple[str, str]],
) -> dict[str, Any]:
    m = default_model_state(1)
    m["title"] = assign_name or defn_name
    lines = [f"Assignment: {assign_name}"]
    if defn_name:
        lines.insert(0, f"Definition: {defn_name}")
    for agent, ref in rows:
        a, r = str(agent).strip(), str(ref).strip()
        if a or r:
            lines.append(f"  {a or '?'} → {r or '?'}")
    m["description"] = "\n".join(lines)

    if block.get("model_type") is not None:
        m["model_type"] = str(block["model_type"])
    if block.get("batch_size") is not None:
        m["batch_size"] = str(block["batch_size"])
    opt = block.get("optimizer")
    if isinstance(opt, dict):
        if opt.get("type") is not None:
            m["optimizer"] = str(opt["type"])
        if opt.get("lr") is not None:
            m["lr"] = str(opt["lr"])
        if opt.get("momentum") is not None:
            m["momentum"] = str(opt["momentum"])
    crit = block.get("criterion")
    if isinstance(crit, dict) and crit.get("type") is not None:
        m["criterion"] = str(crit["type"])
    return m


def _models_preview(
    assignments_document: dict[str, Any] | None,
    definitions_document: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(assignments_document, dict):
        return [default_model_state(1)]

    defn_map = {
        name: block for name, block in definition_entries_from_document(definitions_document or {}).get("models", [])
    }
    assign_entries = assignment_entries_from_document(assignments_document).get("model", [])
    if not assign_entries:
        if defn_map:
            return [_definition_to_model_gui(name, block, name, []) for name, block in defn_map.items()]
        return [default_model_state(1)]

    models: list[dict[str, Any]] = []
    for assign_name, rows in assign_entries:
        primary_ref = next((str(r).strip() for _a, r in rows if str(r).strip()), "")
        block = defn_map.get(primary_ref, {})
        models.append(_definition_to_model_gui(primary_ref, block, assign_name, rows))
    return models or [default_model_state(1)]


def build_experiment_preview(snapshot: YamlStackSnapshot) -> dict[str, Any]:
    """
    Build Experiment-tab display state from the YAML stack (read-only preview).

    Returns partial experiment state plus ``sources`` metadata for UI labels.
    """
    sources = {
        "topology": _source_label(snapshot.topologies_path, "topologies.yaml"),
        "profiles": _source_label(snapshot.assignments_path, "assignments.yaml")
        + " + "
        + _source_label(snapshot.definitions_path, "definitions.yaml").replace("Source: ", ""),
        "models": _source_label(snapshot.assignments_path, "assignments.yaml")
        + " + "
        + _source_label(snapshot.definitions_path, "definitions.yaml").replace("Source: ", ""),
        "network": _source_label(snapshot.network_path, "network.yaml"),
    }
    # Clean combined labels
    sources["profiles"] = (
        f"Source: assignments.yaml + definitions.yaml"
        if snapshot.assignments_path or snapshot.definitions_path
        else "Source: assignments.yaml + definitions.yaml (not loaded)"
    )
    if snapshot.assignments_path and snapshot.definitions_path:
        sources["profiles"] = (
            f"Source: {snapshot.assignments_path.name} + {snapshot.definitions_path.name}"
        )
        sources["models"] = sources["profiles"]

    net_doc = snapshot.network_document if isinstance(snapshot.network_document, dict) else {}
    return {
        "topology": _topology_preview(snapshot.topologies_document),
        "profiles": _profiles_preview(snapshot.assignments_document, snapshot.definitions_document),
        "models": _models_preview(snapshot.assignments_document, snapshot.definitions_document),
        "network_config": dict(net_doc) if net_doc else {},
        "sources": sources,
    }


def _topologies_entries(document: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(document, dict):
        return []
    return [(name, topology_block(document, name)) for name in topology_names(document)]


def validate_yaml_stack(snapshot: YamlStackSnapshot) -> list[str]:
    """Return user-friendly validation errors for the loaded YAML stack (empty if OK)."""
    errors: list[str] = []

    if snapshot.driver_path is None or not isinstance(snapshot.driver_document, dict):
        errors.append("Load driver.yaml before running with the YAML configuration stack.")
        return errors

    driver_vals = gui_values_from_document(snapshot.driver_document)
    ok, driver_errs = validate_driver_values(driver_vals)
    if not ok:
        errors.extend(f"Driver: {e}" for e in driver_errs)

    if snapshot.topologies_path is None:
        errors.append("Topologies: topologies.yaml is not loaded (set paths.topologies in driver.yaml).")
    else:
        topo_entries = _topologies_entries(snapshot.topologies_document)
        if not topo_entries:
            errors.append("Topologies: topologies.yaml contains no topology definitions.")
        else:
            ok, topo_errs = validate_topologies_collection(topo_entries)
            if not ok:
                errors.extend(f"Topologies: {e}" for e in topo_errs)

    if snapshot.definitions_path is None:
        errors.append("Definitions: definitions.yaml is not loaded (set paths.definitions in driver.yaml).")
    else:
        defn_sections = definition_entries_from_document(snapshot.definitions_document or {})
        ok, defn_errs = validate_definition_sections(defn_sections)
        if not ok:
            errors.extend(f"Definitions: {e}" for e in defn_errs)

    if snapshot.assignments_path is None:
        errors.append("Assignments: assignments.yaml is not loaded (set paths.assignments in driver.yaml).")
    else:
        assign_sections = assignment_entries_from_document(snapshot.assignments_document or {})
        defn_refs = (
            reference_names_from_definitions(snapshot.definitions_document or {})
            if snapshot.definitions_path
            else None
        )
        ok, assign_errs = validate_assignment_sections(assign_sections, definition_refs=defn_refs)
        if not ok:
            errors.extend(f"Assignments: {e}" for e in assign_errs)

    # network.yaml is optional: models now live in definitions.yaml, so the
    # stack is valid without it. When present, only its optimizers/criteria are
    # validated.
    if snapshot.network_path is not None:
        net_state = network_gui_state_from_document(snapshot.network_document or {})
        ok, net_errs = validate_network_state(
            optimizers=net_state.get("optimizers", []),
            criteria=net_state.get("criteria", []),
        )
        if not ok:
            errors.extend(f"Network: {e}" for e in net_errs)

    return errors

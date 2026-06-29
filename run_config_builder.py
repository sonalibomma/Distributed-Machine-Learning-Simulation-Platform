from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from math import prod
from pathlib import Path
from typing import Any

from assignments_io import (
    ASSIGNMENT_DEFINITION_SECTION,
    ASSIGNMENT_SECTIONS,
    section_entries_from_document as assignment_entries_from_document,
    section_spec as assignment_section_spec,
)
from definitions_io import section_entries_from_document as definition_entries_from_document
from permutations_io import PERMUTATION_SECTIONS, selections_from_document
from topologies_io import topology_names
from yaml_stack_sync import YamlStackSnapshot, validate_yaml_stack


PERMUTATION_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("topology", "Topologies"),
    ("profile", "Profiles"),
    ("grouping", "Groupings"),
    ("distribution", "Distributions"),
    ("communication", "Communications"),
    ("model", "Models"),
)


@dataclass
class RunStackSnapshot(YamlStackSnapshot):
    """YAML stack plus permutation selections from the Permutations page."""

    permutations_path: Path | None = None
    permutations_document: dict[str, Any] | None = None
    permutation_selections: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class RunConfiguration:
    """In-memory run plan: selected permutation axes and full combination list."""

    paths: dict[str, str]
    selections: dict[str, list[str]]
    selection_counts: dict[str, int]
    combinations: list[dict[str, str]]
    estimated_run_count: int
    driver: dict[str, Any] = field(default_factory=dict)
    permutations: dict[str, Any] = field(default_factory=dict)
    topologies: dict[str, Any] = field(default_factory=dict)
    assignments: dict[str, Any] = field(default_factory=dict)
    definitions: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "paths": copy.deepcopy(self.paths),
            "selections": copy.deepcopy(self.selections),
            "selection_counts": copy.deepcopy(self.selection_counts),
            "combinations": copy.deepcopy(self.combinations),
            "estimated_run_count": self.estimated_run_count,
        }


def _path_str(path: Path | None) -> str:
    return str(path) if path else ""


def _ordered_selections(raw: dict[str, set[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, _label in PERMUTATION_DIMENSIONS:
        chosen = sorted(str(x) for x in raw.get(key, set()) if str(x).strip())
        out[key] = chosen
    return out


def _assignment_map(document: dict[str, Any] | None) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """section_key -> {assignment_name: rows}."""
    out: dict[str, dict[str, list[tuple[str, str]]]] = {
        sec["key"]: {} for sec in ASSIGNMENT_SECTIONS
    }
    if not isinstance(document, dict):
        return out
    entries = assignment_entries_from_document(document)
    for sec in ASSIGNMENT_SECTIONS:
        key = sec["key"]
        for name, rows in entries.get(key, []):
            out[key][str(name)] = list(rows)
    return out


def _definition_name_sets(document: dict[str, Any] | None) -> dict[str, set[str]]:
    entries = definition_entries_from_document(document or {})
    return {key: {str(n) for n, _ in entries.get(key, [])} for key in entries}


def _refs_for_assignment(
    assign_map: dict[str, dict[str, list[tuple[str, str]]]],
    section_key: str,
    assign_name: str,
) -> list[str]:
    spec = assignment_section_spec(section_key)
    ref_field = str(spec["ref_field"])
    rows = assign_map.get(section_key, {}).get(assign_name, [])
    refs: list[str] = []
    for _agent, ref in rows:
        r = str(ref).strip()
        if r:
            refs.append(r)
    if not refs:
        return []
    return refs


def _cartesian_combinations(selections: dict[str, list[str]]) -> list[dict[str, str]]:
    axes = [key for key, _ in PERMUTATION_DIMENSIONS]
    pools: list[list[str]] = []
    for key in axes:
        chosen = selections.get(key, [])
        pools.append(chosen if chosen else [""])
    combos: list[dict[str, str]] = []
    for tpl in itertools.product(*pools):
        combos.append(dict(zip(axes, tpl)))
    return combos


def build_run_configuration(snapshot: RunStackSnapshot) -> RunConfiguration:
    """Build run configuration from loaded YAML documents and permutation selections."""
    selections = _ordered_selections(snapshot.permutation_selections)
    counts = {key: len(selections.get(key, [])) for key, _ in PERMUTATION_DIMENSIONS}
    factors = [counts.get(key, 0) for key, _ in PERMUTATION_DIMENSIONS]
    if all(n > 0 for n in factors):
        estimated = prod(factors)
    else:
        estimated = 0
    combinations = _cartesian_combinations(selections)

    return RunConfiguration(
        paths={
            "driver": _path_str(snapshot.driver_path),
            "permutations": _path_str(snapshot.permutations_path),
            "topologies": _path_str(snapshot.topologies_path),
            "assignments": _path_str(snapshot.assignments_path),
            "definitions": _path_str(snapshot.definitions_path),
            "network": _path_str(snapshot.network_path),
        },
        selections=selections,
        selection_counts=counts,
        combinations=combinations,
        estimated_run_count=estimated,
        driver=copy.deepcopy(snapshot.driver_document or {}),
        permutations=copy.deepcopy(snapshot.permutations_document or {}),
        topologies=copy.deepcopy(snapshot.topologies_document or {}),
        assignments=copy.deepcopy(snapshot.assignments_document or {}),
        definitions=copy.deepcopy(snapshot.definitions_document or {}),
        network=copy.deepcopy(snapshot.network_document or {}),
    )


def validate_run_configuration(snapshot: RunStackSnapshot, config: RunConfiguration) -> list[str]:
    """Validate permutation selections against loaded YAML references."""
    errors: list[str] = list(validate_yaml_stack(snapshot))

    if snapshot.permutations_path is None:
        errors.append("Permutations: permutations.yaml is not loaded (set paths.permutations in driver.yaml).")
        return errors

    topo_names = set(topology_names(snapshot.topologies_document or {}))
    assign_map = _assignment_map(snapshot.assignments_document)
    defn_names = _definition_name_sets(snapshot.definitions_document)

    for key, label in PERMUTATION_DIMENSIONS:
        chosen = config.selections.get(key, [])
        if not chosen:
            errors.append(f"Permutations: no {label.lower()} selected.")
            continue

        if key == "topology":
            for name in chosen:
                if name not in topo_names:
                    errors.append(
                        f"Permutations: selected topology {name!r} was not found in topologies.yaml."
                    )
            continue

        if key not in assign_map:
            continue
        section_assignments = assign_map[key]
        defn_key = ASSIGNMENT_DEFINITION_SECTION[key]
        known_defs = defn_names.get(defn_key, set())

        for assign_name in chosen:
            if assign_name not in section_assignments:
                errors.append(
                    f"Permutations: selected {label.lower()} assignment {assign_name!r} "
                    f"was not found in assignments.yaml."
                )
                continue
            refs = _refs_for_assignment(assign_map, key, assign_name)
            if not refs:
                errors.append(
                    f"Permutations: assignment {assign_name!r} has no reference entries in assignments.yaml."
                )
                continue
            for ref in refs:
                if ref not in known_defs:
                    errors.append(
                        f"Permutations: assignment {assign_name!r} references definition {ref!r}, "
                        f"which was not found in definitions.yaml ({defn_key})."
                    )

    if config.estimated_run_count <= 0:
        errors.append("Permutations: estimated run count must be at least 1.")

    return errors


def format_run_config_preview(config: RunConfiguration) -> str:
    """Multi-line summary for the Run Configuration Preview panel."""
    lines = ["Run Configuration Preview", ""]
    for key, label in PERMUTATION_DIMENSIONS:
        chosen = config.selections.get(key, [])
        count = config.selection_counts.get(key, len(chosen))
        if chosen:
            names = ", ".join(chosen[:8])
            if len(chosen) > 8:
                names += f", … (+{len(chosen) - 8} more)"
            lines.append(f"Selected {label}: {names}")
        else:
            lines.append(f"Selected {label}: (none)")
        lines.append(f"{label}: {count}")
        lines.append("")

    lines.append(f"Estimated Runs: {config.estimated_run_count}")
    return "\n".join(lines).strip()


def build_and_validate_run_configuration(
    snapshot: RunStackSnapshot,
) -> tuple[RunConfiguration | None, list[str]]:
    """Build run configuration and return (config, errors). Config is None if errors exist."""
    config = build_run_configuration(snapshot)
    errors = validate_run_configuration(snapshot, config)
    if errors:
        return None, errors
    return config, []

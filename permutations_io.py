"""Load, validate, and save permutations.yaml for the simulation platform."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from experiment_io import read_yaml_file, write_yaml_file
from path_resolution import resolve_stack_path

PERMUTATIONS_FILENAME = "permutations.yaml"

# GUI section keys mapped to YAML paths and reference-file locations.
PERMUTATION_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "topology",
        "title": "Topology permutations",
        "selected_path": ("permutations", "topologies"),
        "options_path": ("topologies",),
        "ref_driver_key": "paths_topologies",
    },
    {
        "key": "profile",
        "title": "Profile permutations",
        "selected_path": ("permutations", "assignments", "profile"),
        "options_path": ("assignments", "profile"),
        "ref_driver_key": "paths_assignments",
    },
    {
        "key": "grouping",
        "title": "Grouping permutations",
        "selected_path": ("permutations", "assignments", "grouping"),
        "options_path": ("assignments", "grouping"),
        "ref_driver_key": "paths_assignments",
    },
    {
        "key": "distribution",
        "title": "Distribution permutations",
        "selected_path": ("permutations", "assignments", "data_distribution"),
        "options_path": ("assignments", "data_distribution"),
        "ref_driver_key": "paths_assignments",
    },
    {
        "key": "communication",
        "title": "Communication permutations",
        "selected_path": ("permutations", "assignments", "communication_policy"),
        "options_path": ("assignments", "communication_policy"),
        "ref_driver_key": "paths_assignments",
    },
    {
        "key": "model",
        "title": "Model permutations",
        "selected_path": ("permutations", "assignments", "model"),
        "options_path": ("assignments", "model"),
        "ref_driver_key": "paths_assignments",
    },
)


def default_permutations_document() -> dict[str, Any]:
    return {
        "permutations": {
            "topologies": [],
            "assignments": {
                "profile": [],
                "grouping": [],
                "data_distribution": [],
                "model": [],
                "communication_policy": [],
            },
        }
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


def _yaml_path_str(path: tuple[str, ...]) -> str:
    return ".".join(path)


def _keys_from_mapping_block(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return []
    return [str(k) for k in raw.keys()]


def discover_options_from_reference(
    *,
    topologies_path: Path | str | None,
    assignments_path: Path | str | None,
) -> dict[str, list[str]]:
    """Return ordered option names for each permutation section from reference YAML files."""
    out: dict[str, list[str]] = {sec["key"]: [] for sec in PERMUTATION_SECTIONS}

    if topologies_path:
        p = Path(topologies_path)
        if p.is_file():
            raw = read_yaml_file(p)
            block = _dig(raw, ("topologies",))
            out["topology"] = _keys_from_mapping_block(block)

    if assignments_path:
        p = Path(assignments_path)
        if p.is_file():
            raw = read_yaml_file(p)
            for sec in PERMUTATION_SECTIONS:
                if sec["key"] == "topology":
                    continue
                block = _dig(raw, sec["options_path"])
                out[sec["key"]] = _keys_from_mapping_block(block)

    return out


def _merge_option_lists(
    reference: list[str],
    selected: list[str],
    from_document: list[str],
) -> list[str]:
    """Union of known keys, preserving reference order then document-only keys."""
    seen: set[str] = set()
    ordered: list[str] = []
    for name in reference + from_document + selected:
        s = str(name)
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def all_options_for_sections(
    document: dict[str, Any],
    reference_options: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Build complete checkbox option lists (reference keys + any keys already in permutations.yaml)."""
    ref = reference_options or {}
    out: dict[str, list[str]] = {}
    for sec in PERMUTATION_SECTIONS:
        key = sec["key"]
        selected_raw = _dig(document, sec["selected_path"])
        selected = [str(x) for x in selected_raw] if isinstance(selected_raw, list) else []
        out[key] = _merge_option_lists(ref.get(key, []), selected, selected)
    return out


def selections_from_document(document: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for sec in PERMUTATION_SECTIONS:
        raw = _dig(document, sec["selected_path"])
        if isinstance(raw, list):
            out[sec["key"]] = {str(x) for x in raw}
        else:
            out[sec["key"]] = set()
    return out


def merge_selections_into_document(
    base: dict[str, Any],
    all_options: dict[str, list[str]],
    selections: dict[str, set[str]],
) -> dict[str, Any]:
    """Write checkbox state back into a permutations.yaml document."""
    out = copy.deepcopy(base) if isinstance(base, dict) else default_permutations_document()
    for sec in PERMUTATION_SECTIONS:
        key = sec["key"]
        chosen = selections.get(key, set())
        ordered = all_options.get(key, [])
        values = [name for name in ordered if name in chosen]
        parent = _ensure_path(out, sec["selected_path"])
        parent[sec["selected_path"][-1]] = values
    return out


def resolve_permutations_path(
    path_str: str,
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    """Resolve permutations.yaml path; fall back to driver.yaml directory."""
    return resolve_stack_path(path_str, PERMUTATIONS_FILENAME, driver_file=driver_file)


def load_permutations_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_permutations_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")

    merged = default_permutations_document()
    perm_raw = raw.get("permutations")
    if isinstance(perm_raw, dict):
        merged_perm = merged["permutations"]
        for key, val in perm_raw.items():
            if key == "assignments" and isinstance(val, dict):
                assign = merged_perm["assignments"]
                if isinstance(assign, dict):
                    assign.update(copy.deepcopy(val))
            else:
                merged_perm[key] = copy.deepcopy(val)
    else:
        for key, val in raw.items():
            merged[key] = copy.deepcopy(val)

    merged["_source_path"] = str(path.resolve())
    return merged


def save_permutations_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def print_permutations_load_report(
    document: dict[str, Any],
    *,
    source: Path | str | None = None,
    all_options: dict[str, list[str]] | None = None,
) -> None:
    src = f" ({source})" if source else ""
    print(f"\n=== Permutations YAML structure{src} ===")
    selections = selections_from_document(document)
    opts = all_options or all_options_for_sections(document)
    for sec in PERMUTATION_SECTIONS:
        key = sec["key"]
        names = opts.get(key, [])
        chosen = selections.get(key, set())
        print(f"{sec['title']} ({_yaml_path_str(sec['selected_path'])}):")
        for name in names:
            mark = "✓" if name in chosen else " "
            print(f"  [{mark}] {name}")
        if not names:
            print("  (no options discovered)")
    print()

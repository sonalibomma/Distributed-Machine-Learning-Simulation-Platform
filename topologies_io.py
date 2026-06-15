"""Load, validate, and save topologies.yaml for the simulation platform."""

from __future__ import annotations

import ast
import copy
import re
from pathlib import Path
from typing import Any

from experiment_data import graph_type_canonical
from experiment_io import read_yaml_file, write_yaml_file
from path_resolution import resolve_stack_path

TOPOLOGIES_FILENAME = "topologies.yaml"

# Topologies page: canonical GUI ids and user-facing labels.
TOPO_PAGE_GRAPH_TYPES: tuple[str, ...] = (
    "complete",
    "er",
    "ws",
    "ba",
    "stochastic_block_model",
    "star",
)

TOPO_PAGE_GRAPH_LABELS: dict[str, str] = {
    "complete": "Complete Graph",
    "er": "Erdos-Renyi Graph",
    "ws": "Watts-Strogatz Graph",
    "ba": "Barabasi-Albert Graph",
    "stochastic_block_model": "Stochastic Block Model",
    "star": "Star Graph",
}

# Backend graph_type strings used in topologies.yaml (preserve on save).
CANONICAL_TO_YAML_GRAPH_TYPE: dict[str, str] = {
    "complete": "complete",
    "er": "erdos_renyi",
    "ws": "watts_strogatz",
    "ba": "barabasi_albert",
    "stochastic_block_model": "stochastic_block_model",
    "star": "star",
}

YAML_TO_CANONICAL_GRAPH_TYPE: dict[str, str] = {
    "complete": "complete",
    "erdos_renyi": "er",
    "erdos-renyi": "er",
    "er": "er",
    "watts_strogatz": "ws",
    "watts-strogatz": "ws",
    "ws": "ws",
    "barabasi_albert": "ba",
    "barabasi-albert": "ba",
    "ba": "ba",
    "stochastic_block_model": "stochastic_block_model",
    "sbm": "stochastic_block_model",
    "star": "star",
}

# Primary parameter keys per graph type (seed is optional).
GRAPH_TYPE_PARAM_KEYS: dict[str, tuple[str, ...]] = {
    "complete": ("n",),
    "er": ("n", "p", "seed"),
    "ws": ("n", "k", "p", "seed"),
    "ba": ("n", "m", "seed"),
    "stochastic_block_model": ("sizes", "p", "seed"),
    "star": ("n",),
}

PROBABILITY_PARAM_KEYS = frozenset({"p"})
POSITIVE_INT_PARAM_KEYS = frozenset({"n", "k", "m"})


def topo_page_graph_display_values() -> tuple[str, ...]:
    return tuple(TOPO_PAGE_GRAPH_LABELS[k] for k in TOPO_PAGE_GRAPH_TYPES)


def canonical_to_display(canonical: str) -> str:
    gt = graph_type_canonical(canonical)
    if gt in TOPO_PAGE_GRAPH_LABELS:
        return TOPO_PAGE_GRAPH_LABELS[gt]
    from experiment_data import graph_type_label

    label = graph_type_label(gt)
    if not label.endswith("Graph"):
        return f"{label} Graph"
    return label


def display_to_canonical(display: str) -> str:
    s = str(display).strip()
    for key, label in TOPO_PAGE_GRAPH_LABELS.items():
        if label.lower() == s.lower():
            return key
    return graph_type_canonical(s)


def yaml_graph_type_from_canonical(canonical: str) -> str:
    gt = graph_type_canonical(canonical)
    if gt in CANONICAL_TO_YAML_GRAPH_TYPE:
        return CANONICAL_TO_YAML_GRAPH_TYPE[gt]
    return gt


def canonical_from_yaml_graph_type(raw: Any) -> str:
    if raw is None:
        return TOPO_PAGE_GRAPH_TYPES[0]
    key = str(raw).strip().lower().replace("-", "_")
    if key in YAML_TO_CANONICAL_GRAPH_TYPE:
        return YAML_TO_CANONICAL_GRAPH_TYPE[key]
    return graph_type_canonical(raw)


def default_topologies_document() -> dict[str, Any]:
    return {
        "topologies": {},
        "topology_analytics": {
            "display_type": {"type": "spring", "seed": 10396953},
            "rank_by_centrality": {"top": {"percentage": 10}, "bottom": {"count": 10}},
        },
    }


def default_topology_block(graph_type: str = "complete") -> dict[str, Any]:
    gt = graph_type_canonical(graph_type)
    block: dict[str, Any] = {"graph_type": yaml_graph_type_from_canonical(gt)}
    if gt == "complete":
        block["n"] = 50
    elif gt == "er":
        block.update({"n": 50, "p": 0.5, "seed": 0})
    elif gt == "ws":
        block.update({"n": 50, "k": 5, "p": 0.5, "seed": 0})
    elif gt == "ba":
        block.update({"n": 50, "m": 5, "seed": 0})
    elif gt == "stochastic_block_model":
        block.update({"sizes": [1, 1], "p": [[0.5, 0.5], [0.5, 0.5]], "seed": 0})
    elif gt == "star":
        block["n"] = 50
    else:
        block["n"] = 50
    return block


def resolve_topologies_path(
    path_str: str,
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    """Resolve topologies.yaml path; fall back to driver.yaml directory."""
    return resolve_stack_path(path_str, TOPOLOGIES_FILENAME, driver_file=driver_file)


def load_topologies_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_topologies_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")

    merged = default_topologies_document()
    if isinstance(raw.get("topologies"), dict):
        merged["topologies"] = copy.deepcopy(raw["topologies"])
    if isinstance(raw.get("topology_analytics"), dict):
        merged["topology_analytics"] = copy.deepcopy(raw["topology_analytics"])

    for key, val in raw.items():
        if key not in merged:
            merged[key] = copy.deepcopy(val)

    merged["_source_path"] = str(path.resolve())
    return merged


def save_topologies_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def topology_names(document: dict[str, Any]) -> list[str]:
    block = document.get("topologies")
    if not isinstance(block, dict):
        return []
    return list(block.keys())


def topology_block(document: dict[str, Any], name: str) -> dict[str, Any]:
    block = document.get("topologies")
    if not isinstance(block, dict):
        return default_topology_block()
    entry = block.get(name)
    if isinstance(entry, dict):
        return copy.deepcopy(entry)
    return default_topology_block()


def format_param_for_display(key: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return repr(value)
    return str(value)


def parse_param_value(key: str, text: str) -> Any:
    s = str(text).strip()
    if not s:
        return None
    if key in {"sizes", "p"} or s.startswith(("[", "{")):
        try:
            return ast.literal_eval(s)
        except (SyntaxError, ValueError):
            if key == "sizes":
                parts = [p.strip() for p in s.split(",") if p.strip()]
                return [int(float(p)) for p in parts]
            raise ValueError(f"Could not parse {key!r} value: {s!r}")
    if key in POSITIVE_INT_PARAM_KEYS or key == "seed":
        if re.match(r"^-?\d+$", s):
            return int(s)
        if re.match(r"^-?\d+\.0+$", s):
            return int(float(s))
        return int(float(s))
    if key in PROBABILITY_PARAM_KEYS:
        return float(s)
    try:
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    except ValueError:
        return s


def param_keys_for_block(block: dict[str, Any]) -> tuple[str, ...]:
    gt = canonical_from_yaml_graph_type(block.get("graph_type"))
    primary = GRAPH_TYPE_PARAM_KEYS.get(gt, ("n",))
    extras = [k for k in block if k != "graph_type" and k not in primary]
    return tuple(primary) + tuple(extras)


def extra_param_keys(block: dict[str, Any], canonical_gt: str) -> list[str]:
    primary = set(GRAPH_TYPE_PARAM_KEYS.get(canonical_gt, ()))
    return [k for k in block if k != "graph_type" and k not in primary]


def block_from_gui(
    *,
    graph_type_display: str,
    param_text: dict[str, str],
    extra_param_text: dict[str, str] | None = None,
) -> dict[str, Any]:
    canonical = display_to_canonical(graph_type_display)
    out: dict[str, Any] = {"graph_type": yaml_graph_type_from_canonical(canonical)}
    keys = list(GRAPH_TYPE_PARAM_KEYS.get(canonical, ()))
    if extra_param_text:
        keys.extend(k for k in extra_param_text if k not in keys)
    for key in keys:
        if key not in param_text and (not extra_param_text or key not in extra_param_text):
            continue
        raw = param_text.get(key, extra_param_text.get(key, "") if extra_param_text else "")
        if str(raw).strip() == "" and key == "seed":
            continue
        if str(raw).strip() == "":
            continue
        out[key] = parse_param_value(key, raw)
    return out


def validate_topology_entry(name: str, block: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nm = str(name).strip()
    if not nm:
        errors.append("Topology name cannot be empty.")
        return errors

    gt_raw = block.get("graph_type")
    if not gt_raw:
        errors.append(f"Topology {nm!r} is missing graph type.")
        return errors

    canonical = canonical_from_yaml_graph_type(gt_raw)
    required = [k for k in GRAPH_TYPE_PARAM_KEYS.get(canonical, ("n",)) if k != "seed"]

    for key in required:
        if key not in block or block[key] is None or str(block[key]).strip() == "":
            label = canonical_to_display(canonical)
            errors.append(f"Topology {nm!r} is missing required parameter {key} ({label}).")

    for key in POSITIVE_INT_PARAM_KEYS:
        if key not in block:
            continue
        try:
            val = int(block[key])
        except (TypeError, ValueError):
            errors.append(f"Topology {nm!r}: parameter {key} must be a positive integer.")
            continue
        if val <= 0:
            errors.append(f"Topology {nm!r}: parameter {key} must be a positive integer.")

    if canonical == "ws" and "k" in block:
        try:
            k_val = int(block["k"])
            if k_val <= 0:
                errors.append(f"Topology {nm!r}: Watts-Strogatz parameter k must be a positive integer.")
        except (TypeError, ValueError):
            errors.append(f"Topology {nm!r}: Watts-Strogatz parameter k must be a positive integer.")

    for key in PROBABILITY_PARAM_KEYS:
        if key not in block:
            continue
        try:
            p_val = float(block[key])
        except (TypeError, ValueError):
            if isinstance(block[key], list):
                continue
            errors.append(f"Topology {nm!r}: parameter {key} must be a number between 0 and 1.")
            continue
        if isinstance(block[key], (int, float)) and not 0.0 <= p_val <= 1.0:
            errors.append(f"Topology {nm!r}: parameter {key} must be between 0 and 1.")

    if "seed" in block and block["seed"] is not None and str(block["seed"]).strip() != "":
        try:
            int(block["seed"])
        except (TypeError, ValueError):
            errors.append(f"Topology {nm!r}: seed must be an integer.")

    return errors


def validate_topologies_collection(entries: list[tuple[str, dict[str, Any]]]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    seen: set[str] = set()
    for name, block in entries:
        nm = str(name).strip()
        if nm in seen:
            errors.append(f"Duplicate topology name: {nm!r}.")
        seen.add(nm)
        errors.extend(validate_topology_entry(nm, block))
    return (len(errors) == 0, errors)


def merge_gui_into_document(
    base: dict[str, Any],
    entries: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    out = copy.deepcopy(base) if isinstance(base, dict) else default_topologies_document()
    out["topologies"] = {name: copy.deepcopy(block) for name, block in entries}
    return out


def print_topologies_load_report(document: dict[str, Any], *, source: Path | str | None = None) -> None:
    src = f" ({source})" if source else ""
    print(f"\n=== Topologies YAML structure{src} ===")
    names = topology_names(document)
    print(f"  {len(names)} topology definition(s)")
    for name in names:
        block = topology_block(document, name)
        gt = block.get("graph_type", "?")
        print(f"  - {name}: graph_type={gt!r}")
    analytics = document.get("topology_analytics")
    if isinstance(analytics, dict):
        print("  topology_analytics: preserved")
    print()

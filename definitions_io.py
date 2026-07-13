"""Load, validate, and save definitions.yaml for the simulation platform."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any, Literal

from experiment_io import read_yaml_file, write_yaml_file
from path_resolution import resolve_stack_path

DEFINITIONS_FILENAME = "definitions.yaml"

FieldKind = Literal["text", "number", "bool", "prob", "yaml"]

# (field_key, label, kind)
FieldSpec = tuple[str, str, FieldKind]

DEFINITION_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "agent_profiles",
        "title": "Agent Profiles",
        "yaml_path": ("definitions", "agent_profiles"),
        "add_label": "Add Profile",
        "remove_label": "Remove Profile",
        "default_new_name": "profile_new",
        "fields": (
            ("role", "Role", "text"),
            ("aggregation", "Aggregation", "text"),
            ("wait_time", "Wait Time", "number"),
            ("aggregation_minimum", "Aggregation Minimum", "number"),
            ("aggregation_maximum", "Aggregation Maximum", "number"),
            ("freshness_cap", "Freshness Cap", "number"),
            ("training_time", "Training Time", "number"),
            ("does_train", "Does Train", "bool"),
            ("metrics", "Metrics", "yaml"),
            ("neighbor_ratio", "Neighbor Ratio", "number"),
            ("epochs", "Epochs", "number"),
            ("mini_batches", "Mini Batches", "number"),
            ("release_agent", "Release Agent", "number"),
            ("is_sync", "Is Sync", "bool"),
            ("checkpoint_enabled", "Checkpoint Enabled", "bool"),
        ),
    },
    {
        "key": "groupings",
        "title": "Grouping Profiles",
        "yaml_path": ("definitions", "groupings"),
        "add_label": "Add Grouping",
        "remove_label": "Remove Grouping",
        "default_new_name": "grouping_new",
        "fields": (
            ("grouping_type", "Grouping Type", "text"),
            ("round_start", "Round Start", "number"),
            ("round_end", "Round End", "number"),
        ),
    },
    {
        "key": "data_distributions",
        "title": "Distribution Profiles",
        "yaml_path": ("definitions", "data_distributions"),
        "add_label": "Add Distribution",
        "remove_label": "Remove Distribution",
        "default_new_name": "distribution_new",
        "fields": (
            ("distribution_type", "Distribution Type", "text"),
            ("training", "Training Parameters", "yaml"),
            ("validation", "Validation Parameters", "yaml"),
        ),
    },
    {
        "key": "communication_policies",
        "title": "Communication Profiles",
        "yaml_path": ("definitions", "communication_policies"),
        "add_label": "Add Communication Profile",
        "remove_label": "Remove Communication Profile",
        "default_new_name": "communication_new",
        "fields": (
            ("latency_probability", "Latency Probability", "prob"),
            ("drop_out_probability", "Dropout Probability", "prob"),
            ("latency_minimum", "Latency Minimum", "number"),
            ("latency_maximum", "Latency Maximum", "number"),
            ("interruption_probability", "Interruption Probability", "prob"),
            ("earliest_interruption", "Earliest Interruption", "number"),
            ("latest_interruption", "Latest Interruption", "number"),
        ),
    },
    {
        "key": "models",
        "title": "Model Profiles",
        "yaml_path": ("definitions", "models"),
        "add_label": "Add Model",
        "remove_label": "Remove Model",
        "default_new_name": "model_new",
        "fields": (
            ("model_type", "Model Type", "text"),
            ("batch_size", "Batch Size", "number"),
            ("architecture", "Architecture", "yaml"),
            ("optimizer", "Optimizer", "yaml"),
            ("criterion", "Criteria", "yaml"),
        ),
    },
)

DefinitionEntry = tuple[str, dict[str, Any]]
SectionEntries = dict[str, list[DefinitionEntry]]


def default_definitions_document() -> dict[str, Any]:
    return {
        "definitions": {
            "assignments": {},
            "agent_profiles": {},
            "groupings": {},
            "data_distributions": {},
            "communication_policies": {},
            "models": {},
        }
    }


def section_spec(key: str) -> dict[str, Any]:
    for sec in DEFINITION_SECTIONS:
        if sec["key"] == key:
            return sec
    raise KeyError(key)


def known_field_keys(section_key: str) -> frozenset[str]:
    return frozenset(f[0] for f in section_spec(section_key)["fields"])


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


def resolve_definitions_path(
    path_str: str,
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    return resolve_stack_path(path_str, DEFINITIONS_FILENAME, driver_file=driver_file)


def load_definitions_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_definitions_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")

    merged = default_definitions_document()
    def_raw = raw.get("definitions")
    if isinstance(def_raw, dict):
        def_block = merged["definitions"]
        for key, val in def_raw.items():
            if isinstance(val, dict):
                def_block[key] = copy.deepcopy(val)
            else:
                def_block[key] = copy.deepcopy(val)

    for key, val in raw.items():
        if key not in merged:
            merged[key] = copy.deepcopy(val)

    merged["_source_path"] = str(path.resolve())
    return merged


def save_definitions_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def format_field_value(kind: FieldKind, value: Any) -> str:
    if value is None:
        return ""
    if kind == "bool":
        return "true" if bool(value) else "false"
    if kind == "yaml" or isinstance(value, (dict, list)):
        return repr(value)
    return str(value)


def parse_bool_text(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "yes", "on")


def parse_field_value(kind: FieldKind, text: str) -> Any:
    s = str(text).strip()
    if kind == "bool":
        return parse_bool_text(s)
    if not s:
        return None
    if kind == "yaml" or s.startswith(("{", "[", "(", "'")):
        try:
            return ast.literal_eval(s)
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Invalid YAML/literal value: {s!r}") from e
    if kind == "prob" or kind == "number":
        if s.lstrip("-").isdigit() or (s.count(".") == 1 and s.replace(".", "", 1).lstrip("-").isdigit()):
            return int(s) if s.lstrip("-").isdigit() and "." not in s else float(s)
        return float(s)
    return s


def split_block_fields(section_key: str, block: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    known = known_field_keys(section_key)
    known_vals: dict[str, Any] = {}
    extra_vals: dict[str, Any] = {}
    for key, val in block.items():
        if key in known:
            known_vals[key] = val
        else:
            extra_vals[key] = val
    return known_vals, extra_vals


def default_new_block(section_key: str) -> dict[str, Any]:
    if section_key == "agent_profiles":
        return {
            "role": "p2p",
            "aggregation": "average",
            "wait_time": -1,
            "aggregation_minimum": -1,
            "freshness_cap": -1,
            "training_time": 1,
            "does_train": True,
            "metrics": ["accuracy"],
            "neighbor_ratio": 1,
            "epochs": 5,
            "mini_batches": 20,
            "release_agent": 5,
            "is_sync": True,
            "checkpoint_enabled": False,
        }
    if section_key == "groupings":
        return {"round_start": 0, "round_end": 100}
    if section_key == "data_distributions":
        return {
            "training": {"dataset_start": 0, "dataset_end": 60000, "sampling": 15000},
            "validation": {"dataset_start": 0, "dataset_end": 60000, "sampling": 15000},
        }
    if section_key == "communication_policies":
        return {
            "latency_probability": 0,
            "drop_out_probability": 0,
            "latency_minimum": 1,
            "latency_maximum": 3,
        }
    if section_key == "models":
        return {
            "batch_size": 64,
            "optimizer": {"type": "SGD", "lr": 0.01, "momentum": 0.9},
            "criterion": {"type": "CrossEntropyLoss"},
        }
    return {}


def section_entries_from_document(document: dict[str, Any]) -> SectionEntries:
    out: SectionEntries = {}
    for sec in DEFINITION_SECTIONS:
        key = sec["key"]
        block = _dig(document, sec["yaml_path"])
        entries: list[DefinitionEntry] = []
        if isinstance(block, dict):
            for name, item in block.items():
                if isinstance(item, dict):
                    entries.append((str(name), copy.deepcopy(item)))
        out[key] = entries
    return out


def block_from_gui_fields(
    section_key: str,
    known_values: dict[str, str],
    known_kinds: dict[str, FieldKind],
    extra_values: dict[str, str],
) -> dict[str, Any]:
    block: dict[str, Any] = {}
    for field_key, text in known_values.items():
        kind = known_kinds[field_key]
        if kind == "bool":
            block[field_key] = parse_bool_text(text)
            continue
        if str(text).strip() == "":
            continue
        block[field_key] = parse_field_value(kind, text)

    for field_key, text in extra_values.items():
        fk = str(field_key).strip()
        if not fk:
            continue
        if str(text).strip() == "":
            continue
        ts = str(text).strip()
        try:
            block[fk] = ast.literal_eval(ts)
        except (SyntaxError, ValueError):
            block[fk] = ts
    return block


def merge_sections_into_document(
    base: dict[str, Any],
    sections: SectionEntries,
) -> dict[str, Any]:
    out = copy.deepcopy(base) if isinstance(base, dict) else default_definitions_document()
    if "definitions" not in out or not isinstance(out["definitions"], dict):
        out["definitions"] = default_definitions_document()["definitions"]

    for sec in DEFINITION_SECTIONS:
        key = sec["key"]
        section_map: dict[str, Any] = {}
        for name, block in sections.get(key, []):
            nm = str(name).strip()
            if not nm:
                continue
            section_map[nm] = copy.deepcopy(block)
        parent = _ensure_path(out, sec["yaml_path"])
        parent[sec["yaml_path"][-1]] = section_map

    return out


def validate_sections(sections: SectionEntries) -> tuple[bool, list[str]]:
    errors: list[str] = []
    prob_fields = {
        f[0]
        for sec in DEFINITION_SECTIONS
        for f in sec["fields"]
        if f[2] == "prob"
    }

    for sec in DEFINITION_SECTIONS:
        key = sec["key"]
        title = sec["title"]
        seen: set[str] = set()
        field_kinds = {f[0]: f[2] for f in sec["fields"]}

        for name, block in sections.get(key, []):
            nm = str(name).strip()
            if not nm:
                errors.append(f"{title}: definition name cannot be empty.")
                continue
            if nm in seen:
                errors.append(f"{title}: duplicate definition name {nm!r}.")
            seen.add(nm)

            for fk, kind in field_kinds.items():
                if fk not in block:
                    continue
                val = block[fk]
                if kind == "prob":
                    try:
                        p = float(val)
                    except (TypeError, ValueError):
                        errors.append(f"{title} {nm!r}: {fk.replace('_', ' ')} must be a number between 0 and 1.")
                        continue
                    if not 0.0 <= p <= 1.0:
                        errors.append(f"{title} {nm!r}: {fk.replace('_', ' ')} must be between 0 and 1.")

            for fk, val in block.items():
                if fk in field_kinds and field_kinds[fk] in ("number", "prob"):
                    if val is None or str(val).strip() == "":
                        continue
                    try:
                        float(val)
                    except (TypeError, ValueError):
                        if fk not in prob_fields or not isinstance(val, (int, float)):
                            label = fk.replace("_", " ")
                            errors.append(f"{title} {nm!r}: {label} must be a valid number.")

    return (len(errors) == 0, errors)


def print_definitions_load_report(document: dict[str, Any], *, source: Path | str | None = None) -> None:
    src = f" ({source})" if source else ""
    print(f"\n=== Definitions YAML structure{src} ===")
    entries = section_entries_from_document(document)
    assign_block = _dig(document, ("definitions", "assignments"))
    if isinstance(assign_block, dict) and assign_block:
        print(f"  definitions.assignments: {len(assign_block)} item(s) (preserved, not edited in UI)")
    for sec in DEFINITION_SECTIONS:
        sec_entries = entries.get(sec["key"], [])
        print(f"{sec['title']}: {len(sec_entries)} definition(s)")
    print()

"""Load, validate, and save assignments.yaml for the simulation platform."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from definitions_io import DEFINITION_SECTIONS, section_entries_from_document as definition_entries_from_document
from experiment_io import read_yaml_file, write_yaml_file
from path_resolution import resolve_stack_path

ASSIGNMENTS_FILENAME = "assignments.yaml"

# Assignment section key → definitions.yaml section key.
ASSIGNMENT_DEFINITION_SECTION: dict[str, str] = {
    "profile": "agent_profiles",
    "grouping": "groupings",
    "distribution": "data_distributions",
    "communication": "communication_policies",
    "model": "models",
}

AGENT_SELECTION_PRESETS: tuple[str, ...] = (
    "all_agents",
    "first_half",
    "second_half",
    "first_quarter",
    "second_quarter",
    "third_quarter",
    "fourth_quarter",
)

# GUI section keys mapped to Dylan's assignments.yaml structure.
ASSIGNMENT_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "profile",
        "title": "Profile Assignments",
        "yaml_path": ("assignments", "profile"),
        "ref_field": "profile",
        "ref_label": "Profile Reference",
        "add_label": "Add Profile Assignment",
        "remove_label": "Remove Profile Assignment",
        "default_new_name": "profile_new",
        "default_agent": "all_agents",
        "default_ref": "synchronous",
    },
    {
        "key": "grouping",
        "title": "Grouping Assignments",
        "yaml_path": ("assignments", "grouping"),
        "ref_field": "grouping",
        "ref_label": "Grouping Reference",
        "add_label": "Add Grouping Assignment",
        "remove_label": "Remove Grouping Assignment",
        "default_new_name": "grouping_new",
        "default_agent": "first_half",
        "default_ref": "grouping_all_rounds",
    },
    {
        "key": "distribution",
        "title": "Distribution Assignments",
        "yaml_path": ("assignments", "data_distribution"),
        "ref_field": "distribution",
        "ref_label": "Distribution Reference",
        "add_label": "Add Distribution Assignment",
        "remove_label": "Remove Distribution Assignment",
        "default_new_name": "distribution_new",
        "default_agent": "all_agents",
        "default_ref": "iid",
    },
    {
        "key": "communication",
        "title": "Communication Assignments",
        "yaml_path": ("assignments", "communication_policy"),
        "ref_field": "policy",
        "ref_label": "Communication Reference",
        "add_label": "Add Communication Assignment",
        "remove_label": "Remove Communication Assignment",
        "default_new_name": "communication_new",
        "default_agent": "all_agents",
        "default_ref": "vanilla",
    },
    {
        "key": "model",
        "title": "Model Assignments",
        "yaml_path": ("assignments", "model"),
        "ref_field": "model",
        "ref_label": "Model Reference",
        "add_label": "Add Model Assignment",
        "remove_label": "Remove Model Assignment",
        "default_new_name": "model_new",
        "default_agent": "all_agents",
        "default_ref": "mnist",
    },
)

AssignmentRow = tuple[str, str]
AssignmentEntry = tuple[str, list[AssignmentRow]]
SectionEntries = dict[str, list[AssignmentEntry]]


def default_assignments_document() -> dict[str, Any]:
    return {
        "assignments": {
            "profile": {},
            "grouping": {},
            "data_distribution": {},
            "model": {},
            "communication_policy": {},
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


def section_spec(key: str) -> dict[str, Any]:
    for sec in ASSIGNMENT_SECTIONS:
        if sec["key"] == key:
            return sec
    raise KeyError(key)


def definition_section_title(defn_section_key: str) -> str:
    for sec in DEFINITION_SECTIONS:
        if sec["key"] == defn_section_key:
            return str(sec["title"])
    return defn_section_key.replace("_", " ").title()


def agent_selection_options(agent_count: int | None = None) -> tuple[str, ...]:
    """Preset agent tokens plus numeric agent ids when agent_count is known."""
    options: list[str] = list(AGENT_SELECTION_PRESETS)
    if agent_count is not None and agent_count > 0:
        options.extend(str(i) for i in range(agent_count))
    return tuple(options)


def reference_names_from_definitions(document: dict[str, Any]) -> dict[str, frozenset[str]]:
    """Map each assignment section key to the set of definition names available for references."""
    entries = definition_entries_from_document(document)
    out: dict[str, frozenset[str]] = {}
    for sec in ASSIGNMENT_SECTIONS:
        defn_key = ASSIGNMENT_DEFINITION_SECTION[sec["key"]]
        names = {str(name).strip() for name, _ in entries.get(defn_key, []) if str(name).strip()}
        out[sec["key"]] = frozenset(names)
    return out


def merge_dropdown_values(options: tuple[str, ...] | list[str], current: str) -> tuple[str, ...]:
    """Keep dropdown suggestions while preserving a custom current value."""
    cur = str(current or "").strip()
    merged: list[str] = list(options)
    if cur and cur not in merged:
        merged.append(cur)
    return tuple(merged)


def resolve_assignments_path(
    path_str: str,
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    """Resolve assignments.yaml path; fall back to driver.yaml directory."""
    return resolve_stack_path(path_str, ASSIGNMENTS_FILENAME, driver_file=driver_file)


def load_assignments_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_assignments_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")

    merged = default_assignments_document()
    assign_raw = raw.get("assignments")
    if isinstance(assign_raw, dict):
        merged_assign = merged["assignments"]
        for key, val in assign_raw.items():
            if isinstance(val, dict):
                merged_assign[key] = copy.deepcopy(val)
            else:
                merged_assign[key] = copy.deepcopy(val)

    for key, val in raw.items():
        if key not in merged:
            merged[key] = copy.deepcopy(val)

    merged["_source_path"] = str(path.resolve())
    return merged


def save_assignments_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def yaml_row_to_gui(section_key: str, item: Any) -> AssignmentRow:
    if not isinstance(item, dict):
        return ("", "")
    spec = section_spec(section_key)
    agent = str(item.get("assignment", "") or "")
    ref = str(item.get(spec["ref_field"], "") or "")
    return (agent, ref)


def gui_row_to_yaml(section_key: str, agent: str, ref: str) -> dict[str, str]:
    spec = section_spec(section_key)
    return {spec["ref_field"]: ref.strip(), "assignment": agent.strip()}


def section_entries_from_document(document: dict[str, Any]) -> SectionEntries:
    """Extract GUI-friendly assignment entries from a loaded document."""
    out: SectionEntries = {}
    for sec in ASSIGNMENT_SECTIONS:
        key = sec["key"]
        block = _dig(document, sec["yaml_path"])
        entries: list[AssignmentEntry] = []
        if isinstance(block, dict):
            for name, items in block.items():
                rows: list[AssignmentRow] = []
                if isinstance(items, list):
                    if items:
                        for item in items:
                            rows.append(yaml_row_to_gui(key, item))
                    else:
                        rows = [("", "")]
                elif isinstance(items, dict):
                    rows.append(yaml_row_to_gui(key, items))
                else:
                    rows = [("", "")]
                entries.append((str(name), rows))
        out[key] = entries
    return out


def default_new_assignment(section_key: str) -> AssignmentEntry:
    spec = section_spec(section_key)
    base = spec["default_new_name"]
    return (base, [(spec["default_agent"], spec["default_ref"])])


def merge_sections_into_document(
    base: dict[str, Any],
    sections: SectionEntries,
) -> dict[str, Any]:
    out = copy.deepcopy(base) if isinstance(base, dict) else default_assignments_document()
    assign_root = _ensure_path(out, ("assignments",))
    if "assignments" not in out or not isinstance(out["assignments"], dict):
        out["assignments"] = {}

    for sec in ASSIGNMENT_SECTIONS:
        key = sec["key"]
        section_map: dict[str, list[dict[str, str]]] = {}
        for name, rows in sections.get(key, []):
            nm = str(name).strip()
            if not nm:
                continue
            yaml_rows: list[dict[str, str]] = []
            for agent, ref in rows:
                agent_s = str(agent).strip()
                ref_s = str(ref).strip()
                if not agent_s and not ref_s:
                    continue
                yaml_rows.append(gui_row_to_yaml(key, agent_s, ref_s))
            section_map[nm] = yaml_rows

        parent = _ensure_path(out, sec["yaml_path"])
        parent[sec["yaml_path"][-1]] = section_map

    return out


def validate_sections(
    sections: SectionEntries,
    *,
    definition_refs: dict[str, frozenset[str]] | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for sec in ASSIGNMENT_SECTIONS:
        key = sec["key"]
        title = sec["title"]
        ref_label = str(sec.get("ref_label", "Reference"))
        known_refs = definition_refs.get(key) if definition_refs is not None else None
        defn_title = definition_section_title(ASSIGNMENT_DEFINITION_SECTION[key])
        seen: set[str] = set()
        for name, rows in sections.get(key, []):
            nm = str(name).strip()
            if not nm:
                errors.append(f"{title}: assignment name is required.")
                continue
            if nm in seen:
                errors.append(f"{title}: duplicate assignment name {nm!r}.")
            seen.add(nm)

            active_rows = [
                (str(a).strip(), str(r).strip())
                for a, r in rows
                if str(a).strip() or str(r).strip()
            ]
            if not active_rows:
                continue
            for agent, ref in active_rows:
                if not agent:
                    errors.append(f"{title} {nm!r}: agent selection is required.")
                if not ref:
                    errors.append(f"{title} {nm!r}: reference value is required.")
                elif known_refs is not None and ref not in known_refs:
                    errors.append(
                        f"{title} {nm!r}: {ref_label} {ref!r} was not found in definitions.yaml "
                        f"({defn_title})."
                    )
    return (len(errors) == 0, errors)


def print_assignments_load_report(document: dict[str, Any], *, source: Path | str | None = None) -> None:
    src = f" ({source})" if source else ""
    print(f"\n=== Assignments YAML structure{src} ===")
    entries = section_entries_from_document(document)
    for sec in ASSIGNMENT_SECTIONS:
        sec_entries = entries.get(sec["key"], [])
        print(f"{sec['title']}: {len(sec_entries)} assignment(s)")
        for name, rows in sec_entries:
            active = sum(1 for a, r in rows if a.strip() or r.strip())
            print(f"  - {name}: {active} entry row(s)")
    print()

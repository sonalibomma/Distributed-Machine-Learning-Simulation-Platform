"""Build concrete experiment instances from a validated RunConfiguration."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from assignments_io import (
    ASSIGNMENT_DEFINITION_SECTION,
    section_entries_from_document as assignment_entries_from_document,
)
from definitions_io import section_entries_from_document as definition_entries_from_document
from experiment_data import (
    default_communication_card,
    default_experiment_state,
    default_group_policy_card,
    normalize_topology_graph_block,
)
from run_config_builder import PERMUTATION_DIMENSIONS, RunConfiguration
from topologies_io import canonical_from_yaml_graph_type, topology_block
from yaml_stack_sync import _definition_to_model_gui, _definition_to_profile_gui


@dataclass
class ExperimentInstance:
    """One runnable experiment derived from a permutation combination."""

    index: int
    combination: dict[str, str]
    labels: dict[str, str]
    experiment_state: dict[str, Any]
    paths: dict[str, str] = field(default_factory=dict)

    @property
    def instance_number(self) -> int:
        return self.index + 1

    def display_label(self) -> str:
        parts = [self.labels.get(key, self.combination.get(key, "")) for key, _ in PERMUTATION_DIMENSIONS]
        compact = " / ".join(p for p in parts if p)
        return f"Instance {self.instance_number}: {compact}" if compact else f"Instance {self.instance_number}"

    def as_dict(self) -> dict[str, Any]:
        """Orchestrator-friendly serializable payload."""
        return {
            "index": self.index,
            "instance_number": self.instance_number,
            "combination": copy.deepcopy(self.combination),
            "labels": copy.deepcopy(self.labels),
            "paths": copy.deepcopy(self.paths),
            "experiment_state": copy.deepcopy(self.experiment_state),
        }


def _assignment_rows(
    assignments_document: dict[str, Any] | None,
    section_key: str,
    assign_name: str,
) -> list[tuple[str, str]]:
    entries = assignment_entries_from_document(assignments_document or {})
    for name, rows in entries.get(section_key, []):
        if str(name) == assign_name:
            return list(rows)
    return []


def _definition_block(
    definitions_document: dict[str, Any] | None,
    defn_section_key: str,
    ref_name: str,
) -> dict[str, Any]:
    entries = definition_entries_from_document(definitions_document or {})
    for name, block in entries.get(defn_section_key, []):
        if str(name) == ref_name:
            return copy.deepcopy(block)
    return {}


def _primary_ref(rows: list[tuple[str, str]]) -> str:
    return next((str(r).strip() for _agent, r in rows if str(r).strip()), "")


def _agent_assignment_ranges(rows: list[tuple[str, str]]) -> list[list[str]]:
    out: list[list[str]] = []
    for agent, ref in rows:
        a, r = str(agent).strip(), str(ref).strip()
        if a or r:
            out.append([a, r])
    return out if out else [["", ""]]


def _topology_state_for_name(topologies_document: dict[str, Any], topo_name: str) -> dict[str, Any]:
    block = topology_block(topologies_document, topo_name)
    gt = canonical_from_yaml_graph_type(block.get("graph_type"))
    graph = normalize_topology_graph_block({**block, "graph_type": gt})
    graph["graph_label"] = topo_name
    graph["validation_text"] = f"Validation: permutation instance ({topo_name})"
    return {"graphs": [graph], "active_graph_index": 0, **graph}


def _group_policy_for_assignment(
    assign_name: str,
    rows: list[tuple[str, str]],
    defn_block: dict[str, Any],
    defn_name: str,
) -> dict[str, Any]:
    card = default_group_policy_card(1)
    card["title"] = assign_name or defn_name or card["title"]
    rs = defn_block.get("round_start")
    re = defn_block.get("round_end")
    if rs is not None or re is not None:
        card["rounds"] = [[str(rs if rs is not None else ""), str(re if re is not None else "")]]
    # Page 2 Assignment Start/End are numeric agent ranges only; YAML rows stay in the stack.
    return card


def _communication_for_assignment(
    assign_name: str,
    rows: list[tuple[str, str]],
    defn_block: dict[str, Any],
    defn_name: str,
) -> dict[str, Any]:
    card = default_communication_card(1)
    card["title"] = assign_name or defn_name or card["title"]
    mapping = {
        "latency_probability": "latency_prob",
        "drop_out_probability": "dropout_prob",
        "latency_minimum": "latency_min",
        "latency_maximum": "latency_max",
    }
    for src, dst in mapping.items():
        if defn_block.get(src) is not None:
            card[dst] = str(defn_block[src])
    # Page 2 Assignment Start/End are numeric agent ranges only. YAML agent→reference
    # rows stay in the assignments stack; do not copy them into assignment_ranges.
    return card


def _data_assignment_for_definition(
    assign_name: str,
    rows: list[tuple[str, str]],
    defn_block: dict[str, Any],
    defn_name: str,
) -> dict[str, Any]:
    da: dict[str, list[dict[str, Any]]] = {"training": [], "validation": []}
    assign_ranges = _agent_assignment_ranges(rows)
    for split in ("training", "validation"):
        split_block = defn_block.get(split)
        if not isinstance(split_block, dict):
            continue
        da[split].append(
            {
                "description": f"{assign_name} ({defn_name})" if defn_name else assign_name,
                "sampling": [
                    [
                        str(split_block.get("dataset_start", "")),
                        str(split_block.get("dataset_end", "")),
                        str(split_block.get("sampling", "")),
                    ]
                ],
                "assignment_ranges": copy.deepcopy(assign_ranges),
            }
        )
    return da


def _environment_from_driver(driver_document: dict[str, Any] | None) -> dict[str, str]:
    env = dict(default_experiment_state("")["environment"])
    if not isinstance(driver_document, dict):
        return env
    ec = driver_document.get("experiment_config")
    if isinstance(ec, dict) and ec.get("seed") is not None:
        env["random_seed"] = str(ec["seed"])
    paths = driver_document.get("paths")
    if isinstance(paths, dict):
        if paths.get("assignments"):
            env["agent_assignment_path"] = str(paths["assignments"])
        if paths.get("topologies"):
            env["topology_assignment_path"] = str(paths["topologies"])
    return env


def build_experiment_state_for_combination(
    run_config: RunConfiguration,
    combination: dict[str, str],
    *,
    index: int = 0,
) -> dict[str, Any]:
    """Resolve one permutation combination into a full experiment state dict."""
    topo_name = str(combination.get("topology", "")).strip()
    profile_assign = str(combination.get("profile", "")).strip()
    grouping_assign = str(combination.get("grouping", "")).strip()
    distribution_assign = str(combination.get("distribution", "")).strip()
    communication_assign = str(combination.get("communication", "")).strip()
    model_assign = str(combination.get("model", "")).strip()

    label_parts = [topo_name, profile_assign, grouping_assign, distribution_assign, communication_assign, model_assign]
    state = default_experiment_state(f"Run {index + 1}: {' / '.join(x for x in label_parts if x)}")

    state["environment"] = _environment_from_driver(run_config.driver)
    state["network_config"] = copy.deepcopy(run_config.network) if run_config.network else {}

    if topo_name and isinstance(run_config.topologies, dict):
        state["topology"] = _topology_state_for_name(run_config.topologies, topo_name)

    assignments = run_config.assignments if isinstance(run_config.assignments, dict) else {}
    definitions = run_config.definitions if isinstance(run_config.definitions, dict) else {}

    profile_rows = _assignment_rows(assignments, "profile", profile_assign)
    profile_ref = _primary_ref(profile_rows)
    profile_block = _definition_block(definitions, "agent_profiles", profile_ref)
    state["profiles"] = [_definition_to_profile_gui(profile_ref, profile_block, profile_assign, profile_rows)]

    model_rows = _assignment_rows(assignments, "model", model_assign)
    model_ref = _primary_ref(model_rows)
    model_block = _definition_block(definitions, "models", model_ref)
    state["models"] = [_definition_to_model_gui(model_ref, model_block, model_assign, model_rows)]

    grouping_rows = _assignment_rows(assignments, "grouping", grouping_assign)
    grouping_ref = _primary_ref(grouping_rows)
    grouping_block = _definition_block(definitions, "groupings", grouping_ref)
    state["group_policy_cards"] = [
        _group_policy_for_assignment(grouping_assign, grouping_rows, grouping_block, grouping_ref)
    ]

    distribution_rows = _assignment_rows(assignments, "distribution", distribution_assign)
    distribution_ref = _primary_ref(distribution_rows)
    distribution_block = _definition_block(definitions, "data_distributions", distribution_ref)
    state["data_assignment"] = _data_assignment_for_definition(
        distribution_assign, distribution_rows, distribution_block, distribution_ref
    )

    communication_rows = _assignment_rows(assignments, "communication", communication_assign)
    communication_ref = _primary_ref(communication_rows)
    communication_block = _definition_block(definitions, "communication_policies", communication_ref)
    state["communication_cards"] = [
        _communication_for_assignment(communication_assign, communication_rows, communication_block, communication_ref)
    ]

    state["notes"] = (
        "Generated experiment instance from permutation combination.\n"
        f"Topology: {topo_name}\n"
        f"Profile: {profile_assign}\n"
        f"Grouping: {grouping_assign}\n"
        f"Distribution: {distribution_assign}\n"
        f"Communication: {communication_assign}\n"
        f"Model: {model_assign}"
    )
    return state


def build_experiment_instances(run_config: RunConfiguration) -> list[ExperimentInstance]:
    """Build all experiment instances for a run configuration."""
    instances: list[ExperimentInstance] = []
    for index, combination in enumerate(run_config.combinations):
        labels = {key: str(combination.get(key, "")) for key, _label in PERMUTATION_DIMENSIONS}
        experiment_state = build_experiment_state_for_combination(run_config, combination, index=index)
        instances.append(
            ExperimentInstance(
                index=index,
                combination=dict(combination),
                labels=labels,
                experiment_state=experiment_state,
                paths=copy.deepcopy(run_config.paths),
            )
        )
    return instances


def format_instance_preview(instance: ExperimentInstance) -> str:
    """Multi-line summary for the Experiment Instance panel."""
    lines = [
        f"Instance {instance.instance_number}",
        "",
    ]
    for key, label in PERMUTATION_DIMENSIONS:
        value = instance.labels.get(key) or instance.combination.get(key, "")
        lines.append(f"{label}:")
        lines.append(str(value) if value else "(none)")
        lines.append("")
    return "\n".join(lines).strip()

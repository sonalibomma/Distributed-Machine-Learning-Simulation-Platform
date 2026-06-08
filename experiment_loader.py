from __future__ import annotations

import copy
import logging
import pprint
from pathlib import Path
from typing import Any, Optional

from experiment_io import (
    load_network_config,
    missing_required_files,
    read_required_yaml,
    read_yaml_file,
    TOPOLOGY_YAML,
    AGENT_YAML,
    yaml_path,
)
from experiment_data import (
    GRAPH_TYPES,
    default_communication_card,
    default_experiment_state,
    default_group_policy_card,
    default_model_state,
    default_profile_state,
    default_topology_graph_block,
    environment_from_configuration,
    extract_param_values_from_topology_block,
    normalize_communication_card,
    normalize_group_policy_card,
    normalize_topology_graph_block,
    _communication_cards_from_payload,
    _data_assignment_from_payload,
    _flatten_nested_model,
    _flatten_nested_profile,
    _group_policy_cards_from_payload,
    _models_list_from_payload,
    _profiles_list_from_payload,
)

logger = logging.getLogger("experiment_loader")


BACKEND_GRAPH_TYPE_MAP: dict[str, str] = {
    "mesh": "ws",
    "watts_strogatz": "ws",
    "ws": "ws",
    "er": "er",
    "erdos_renyi": "er",
    "gnp": "er",
    "ba": "ba",
    "barabasi_albert": "ba",
    "ea": "extended_barabasi",
    "extended_attachment": "extended_barabasi",
    "extended_barabasi": "extended_barabasi",
    "complete": "complete",
    "star": "star",
    "path": "path",
    "cycle": "cycle",
}


def debug_print_loaded_files(
    config: dict[str, Any],
    topology: dict[str, Any],
    agent: dict[str, Any],
) -> None:
    for title, data in (
        ("EXPERIMENT", config),
        ("TOPOLOGY", topology),
        ("AGENT_ASSIGNMENT", agent),
    ):
        block = f"\n=== {title} ===\n{pprint.pformat(data, width=120, sort_dicts=False)}\n"
        print(block)
        logger.info(block)


def _prob_str(value: Any) -> str:
    """Convert backend probability (0–1 or 0–100 percent) to GUI string in [0, 1]."""
    if value is None:
        return ""
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return str(value)
    if v > 1.0:
        v = v / 100.0
    return str(min(1.0, max(0.0, v)))


def _backend_assignment_to_ranges(assignment: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    items = assignment if isinstance(assignment, list) else ([assignment] if isinstance(assignment, dict) else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "")).lower()
        if kind == "range" and isinstance(item.get("range"), dict):
            r = item["range"]
            rows.append([str(r.get("start", "")), str(r.get("end", ""))])
        elif kind == "list" and isinstance(item.get("list"), list):
            lst = item["list"]
            if lst:
                rows.append([str(min(lst)), str(max(lst))])
        elif kind == "group" and "group" in item:
            g = item["group"]
            rows.append([str(g), str(g)])
    return rows if rows else [["", ""]]


def _is_backend_topology(raw: dict[str, Any]) -> bool:
    if isinstance(raw.get("parameters"), dict):
        return True
    topo = raw.get("topology")
    return isinstance(topo, list) and bool(topo)


def _is_backend_configuration(raw: dict[str, Any]) -> bool:
    return isinstance(raw.get("save"), dict) or isinstance(raw.get("dir_path"), dict)


def _is_backend_agent(raw: dict[str, Any]) -> bool:
    return (
        isinstance(raw.get("profile_assignment"), list)
        or isinstance(raw.get("model_assignment"), list)
        or isinstance(raw.get("communication_assignment"), list)
    )


def _seed_from_topology_raw(raw: dict[str, Any]) -> Optional[str]:
    analytics = raw.get("analytics")
    if isinstance(analytics, dict):
        display = analytics.get("display_type")
        if isinstance(display, dict) and display.get("seed") is not None:
            return str(display["seed"])
    params = raw.get("parameters")
    if isinstance(params, dict):
        for key in ("seed", "global_seed", "random_seed"):
            if params.get(key) is not None:
                return str(params[key])
    for key in ("global_seed", "seed", "random_seed"):
        if raw.get(key) is not None:
            return str(raw[key])
    return None


def _gui_graph_type(raw_type: Any) -> str:
    gt = str(raw_type or "er").strip().lower()
    mapped = BACKEND_GRAPH_TYPE_MAP.get(gt, gt)
    return mapped if mapped in GRAPH_TYPES else "ws"


def _backend_topology_param_values(params: dict[str, Any], gui_gt: str) -> list[str]:
    n = params.get("node_count", params.get("n", params.get("num_nodes")))
    neighbor = params.get("neighbor_count", params.get("k", params.get("m")))
    p_raw = params.get("edge_probability", params.get("p", params.get("prob")))

    if gui_gt == "ws":
        return [str(n or ""), str(neighbor or ""), _prob_str(p_raw)]
    if gui_gt == "ba":
        return [str(n or ""), str(neighbor or "")]
    if gui_gt == "er":
        return [str(n or ""), _prob_str(p_raw)]
    if n is not None:
        return [str(n)]
    return []


def normalize_topology_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Map backend topology.yaml or GUI topology export to GUI topology state."""
    if _is_backend_topology(raw):
        params = raw.get("parameters") if isinstance(raw.get("parameters"), dict) else {}
        gui_gt = _gui_graph_type(params.get("graph_type"))
        block = default_topology_graph_block()
        block["graph_type"] = gui_gt
        seed = _seed_from_topology_raw(raw)
        if seed is not None:
            block["global_seed"] = seed
        block["param_values"] = _backend_topology_param_values(params, gui_gt)
        return {
            "graphs": [copy.deepcopy(block)],
            "active_graph_index": 0,
            **copy.deepcopy(block),
            "_adjacency_topology": copy.deepcopy(raw.get("topology")) if isinstance(raw.get("topology"), list) else None,
        }

    if isinstance(raw.get("graphs"), list) and raw["graphs"]:
        graphs = [normalize_topology_graph_block(g) for g in raw["graphs"] if isinstance(g, dict)]
        ai = int(raw.get("active_graph_index", 0))
        ai = max(0, min(ai, len(graphs) - 1))
        active = graphs[ai]
        return {"graphs": graphs, "active_graph_index": ai, **copy.deepcopy(active)}

    block = normalize_topology_graph_block(raw)
    return {"graphs": [block], "active_graph_index": 0, **copy.deepcopy(block)}


def normalize_environment_from_config(config: dict[str, Any], folder: Path, topology_raw: dict[str, Any]) -> dict[str, str]:
    env = environment_from_configuration(config)

    if _is_backend_configuration(config):
        save = config.get("save")
        if isinstance(save, dict):
            if save.get("path"):
                env["save_path"] = str(save["path"])
            if save.get("name"):
                env["save_name"] = str(save["name"])
        dir_path = config.get("dir_path")
        if isinstance(dir_path, dict):
            base = str(dir_path.get("path", "")).strip()
            topo_name = str(dir_path.get("topology", TOPOLOGY_YAML)).strip()
            agent_name = str(dir_path.get("agent_assignment", AGENT_YAML)).strip()
            if base:
                env["topology_assignment_path"] = str((Path(base) / topo_name).resolve()) if topo_name else base
                env["agent_assignment_path"] = str((Path(base) / agent_name).resolve()) if agent_name else base

    seed = _seed_from_topology_raw(topology_raw)
    if seed is not None:
        env["random_seed"] = seed

    topo_path = yaml_path(folder, "topology")
    agent_path = yaml_path(folder, "agent_assignment")
    env["topology_assignment_path"] = str(topo_path.resolve())
    env["agent_assignment_path"] = str(agent_path.resolve())
    return env


def normalize_profile_from_raw(item: dict[str, Any], index: int = 1) -> dict[str, Any]:
    flat = _flatten_nested_profile(item)
    prof = item.get("profile")
    if isinstance(prof, dict):
        for k, v in prof.items():
            if k not in flat or flat.get(k) in (None, ""):
                flat[k] = v

    b = default_profile_state(index)
    b["title"] = str(flat.get("title", f"Profile {index}"))
    b["description"] = str(item.get("description", flat.get("description", "")))
    if flat.get("role") is not None:
        b["role"] = str(flat["role"])
    if flat.get("aggregation") is not None:
        b["aggregation"] = str(flat["aggregation"])
    for src, dst in (
        ("wait_time", "wait_time"),
        ("aggregation_minimum", "agg_min"),
        ("agg_min", "agg_min"),
        ("freshness_cap", "freshness_cap"),
        ("training_time", "training_time"),
        ("group", "group_id"),
        ("group_id", "group_id"),
    ):
        if flat.get(src) is not None:
            b[dst] = str(flat[src])
    metrics = flat.get("metrics")
    if isinstance(metrics, list):
        b["metrics"] = ", ".join(str(x) for x in metrics)
    elif metrics is not None:
        b["metrics"] = str(metrics)
    if "does_train" in flat:
        b["does_train"] = bool(flat["does_train"])
    b["assignment_ranges"] = _backend_assignment_to_ranges(item.get("assignment", flat.get("assignment_ranges")))
    return b


def normalize_model_from_raw(item: dict[str, Any], index: int = 1) -> dict[str, Any]:
    flat = _flatten_nested_model(item)
    model = item.get("model")
    if isinstance(model, dict):
        for k, v in model.items():
            key = "model_type" if k == "type" else k
            if key not in flat or flat.get(key) in (None, ""):
                flat[key] = v

    b = default_model_state(index)
    b["title"] = str(flat.get("title", f"Model {index}"))
    b["description"] = str(item.get("description", flat.get("description", "")))
    b["model_type"] = str(flat.get("model_type", flat.get("type", "")))
    b["optimizer"] = str(flat.get("optimizer", ""))
    b["lr"] = str(flat.get("lr", flat.get("learning_rate", "")))
    b["momentum"] = str(flat.get("momentum", ""))
    b["batch_size"] = str(flat.get("batch_size", flat.get("batchsize", "")))
    b["criterion"] = str(flat.get("criterion", ""))
    if flat.get("epochs") is not None:
        b["epochs"] = str(flat["epochs"])
    b["assignment_ranges"] = _backend_assignment_to_ranges(item.get("assignment", flat.get("assignment_ranges")))
    return b


def normalize_communication_from_raw(item: dict[str, Any], index: int = 1) -> dict[str, Any]:
    """Backend cards nest settings under communication: { latency, latency_probability, ... }."""
    inner = item.get("communication")
    merged: dict[str, Any] = dict(item)
    if isinstance(inner, dict):
        merged.update(inner)
        merged["dropout_prob"] = inner.get("drop_out_probability", inner.get("dropout_probability"))
        merged["latency_prob"] = inner.get("latency_probability", inner.get("latency_prob"))
        if inner.get("latency") is not None:
            merged["latency_min"] = str(inner["latency"])
            merged["latency_max"] = str(inner["latency"])

    card = normalize_communication_card(merged, index)
    if merged.get("latency_probability") is not None and not card.get("latency_prob"):
        card["latency_prob"] = _prob_str(merged["latency_probability"])
    if merged.get("drop_out_probability") is not None and not card.get("dropout_prob"):
        card["dropout_prob"] = _prob_str(merged["drop_out_probability"])
    if merged.get("latency_probability") is not None:
        card["latency_prob"] = _prob_str(merged["latency_probability"])
    if merged.get("drop_out_probability") is not None:
        card["dropout_prob"] = _prob_str(merged["drop_out_probability"])

    assign = item.get("assignment")
    if assign is not None:
        card["assignment_ranges"] = _backend_assignment_to_ranges(
            assign if isinstance(assign, list) else [assign]
        )
    return card


def normalize_data_entry(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"description": str(item.get("description", ""))}
    sampling_rows: list[list[str]] = []
    for s in item.get("sampling") or []:
        if isinstance(s, dict) and str(s.get("type", "")).lower() == "range":
            r = s.get("range")
            if isinstance(r, dict):
                sampling_rows.append(
                    [str(r.get("start", "")), str(r.get("end", "")), str(r.get("sampling", ""))]
                )
        elif isinstance(s, dict) and isinstance(s.get("range"), dict):
            r = s["range"]
            sampling_rows.append(
                [str(r.get("start", "")), str(r.get("end", "")), str(r.get("sampling", ""))]
            )
        elif isinstance(s, (list, tuple)):
            sampling_rows.append([str(x) for x in (list(s) + ["", "", ""])[:3]])
    out["sampling"] = sampling_rows if sampling_rows else [["", "", ""]]
    out["assignment_ranges"] = _backend_assignment_to_ranges(item.get("assignment"))
    return out


def normalize_data_assignment_from_raw(agent: dict[str, Any]) -> dict[str, Any]:
    da = agent.get("data_assignment")
    if not isinstance(da, dict):
        return {"training": [], "validation": []}
    out: dict[str, Any] = {"training": [], "validation": []}
    for key in ("training", "validation"):
        entries = da.get(key)
        if isinstance(entries, list):
            out[key] = [normalize_data_entry(x) for x in entries if isinstance(x, dict)]
    return out


def normalize_group_policies(config: dict[str, Any], agent: dict[str, Any]) -> list[dict[str, Any]]:
    gpc = _group_policy_cards_from_payload(config) or _group_policy_cards_from_payload(agent)
    if gpc:
        return [normalize_group_policy_card(x, i + 1) for i, x in enumerate(gpc) if isinstance(x, dict)]

    rounds = config.get("communication_rounds")
    if rounds is not None:
        card = default_group_policy_card(1)
        card["rounds"] = [["0", str(rounds)]]
        return [card]
    return [default_group_policy_card(1)]


def normalize_communications(config: dict[str, Any], agent: dict[str, Any]) -> list[dict[str, Any]]:
    raw_list: Optional[list[dict[str, Any]]] = None
    for src in (agent, config):
        ca = src.get("communication_assignment")
        if isinstance(ca, list) and ca:
            raw_list = [x for x in ca if isinstance(x, dict)]
            break
        cc = _communication_cards_from_payload(src)
        if cc:
            raw_list = cc
            break

    if raw_list:
        if _is_backend_agent(agent) and any(isinstance(x.get("communication"), dict) for x in raw_list):
            return [normalize_communication_from_raw(x, i + 1) for i, x in enumerate(raw_list)]
        return [normalize_communication_card(x, i + 1) for i, x in enumerate(raw_list)]
    return [default_communication_card(1)]


def load_experiment_folder(folder: Path) -> dict[str, Any]:
    """
    Read an experiment folder and return normalized GUI experiment state.

    Returned dict matches _collect_ui_state / _apply_ui_state shape.
    """
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Experiment folder not found:\n{folder}")

    missing = missing_required_files(folder)
    if missing:
        if len(missing) == 1:
            raise ValueError(f"Missing required file:\n\n{missing[0]}")
        raise ValueError(
            "Missing required files in experiment folder:\n\n"
            + "\n".join(missing)
            + f"\n\nFolder: {folder}"
        )

    config_raw = read_required_yaml(folder, "experiment")
    topo_raw = read_required_yaml(folder, "topology")
    agent_raw = read_required_yaml(folder, "agent_assignment")

    if not all(isinstance(x, dict) for x in (config_raw, topo_raw, agent_raw)):
        raise ValueError("All experiment configuration files must contain a mapping at the root.")

    config: dict[str, Any] = config_raw
    topo: dict[str, Any] = topo_raw
    agent: dict[str, Any] = agent_raw

    debug_print_loaded_files(config, topo, agent)

    name = str(config.get("name") or config.get("save", {}).get("name") or folder.name)
    state = default_experiment_state(name)
    state["name"] = name
    state["notes"] = str(config.get("notes") or "")
    state["environment"] = normalize_environment_from_config(config, folder, topo)
    state["topology"] = normalize_topology_from_raw(topo)

    profiles = _profiles_list_from_payload(agent)
    if profiles:
        if _is_backend_agent(agent):
            state["profiles"] = [normalize_profile_from_raw(x, i + 1) for i, x in enumerate(profiles)]
        else:
            state["profiles"] = profiles

    models = _models_list_from_payload(agent)
    if models:
        if _is_backend_agent(agent):
            state["models"] = [normalize_model_from_raw(x, i + 1) for i, x in enumerate(models)]
        else:
            state["models"] = models

    state["communication_cards"] = normalize_communications(config, agent)
    state["group_policy_cards"] = normalize_group_policies(config, agent)

    da = _data_assignment_from_payload(agent)
    if da is not None and not _is_backend_agent(agent):
        state["data_assignment"] = da
    elif _is_backend_agent(agent):
        state["data_assignment"] = normalize_data_assignment_from_raw(agent)

    network = load_network_config(folder)
    if network is not None:
        state["network_config"] = network

    return state


def to_gui_experiment_state(normalized: dict[str, Any]) -> dict[str, Any]:
    """Final pass: ensure topology graphs list and param_values for GUI widgets."""
    st = copy.deepcopy(normalized)
    tp = st.get("topology")
    if isinstance(tp, dict):
        if isinstance(tp.get("graphs"), list) and tp["graphs"]:
            st["topology"]["graphs"] = [
                normalize_topology_graph_block(g) if not g.get("param_values") else g
                for g in tp["graphs"]
                if isinstance(g, dict)
            ]
            for i, g in enumerate(st["topology"]["graphs"]):
                if not g.get("param_values") or not any(str(x).strip() for x in g["param_values"]):
                    st["topology"]["graphs"][i]["param_values"] = extract_param_values_from_topology_block(g)
        else:
            block = normalize_topology_graph_block(tp)
            st["topology"] = {
                "graphs": [block],
                "active_graph_index": 0,
                **block,
            }
    return st

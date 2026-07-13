import copy
from pathlib import Path
from typing import Any, Optional

GRAPH_TYPES = (
    "er",
    "ba",
    "extended_barabasi",
    "ws",
    "complete",
    "complete_bipartite",
    "cycle",
    "path",
    "star",
    "wheel",
    "lollipop",
    "barbell",
    "grid_2d",
    "grid",
    "hypercube",
    "ladder",
    "circular_ladder",
    "trivial",
    "empty",
    "gnp_random",
    "dense_gnm_random",
    "gnm_random",
    "random_regular",
    "random_shell",
    "random_powerlaw_tree",
    "random_powerlaw_tree_sequence",
    "random_geometric",
    "soft_random_geometric",
    "random_lobster",
    "random_interval_graph",
    "random_tree",
    "stochastic_block_model",
    "powerlaw_cluster",
    "connected_watts_strogatz",
    "newman_watts_strogatz",
)

GRAPH_TYPE_LABELS: dict[str, str] = {
    "er": "Erdos-Renyi",
    "ws": "Watts-Strogatz",
    "ba": "Barabasi-Albert",
    "extended_barabasi": "Extended Attachment",
    "complete": "Complete Graph",
    "complete_bipartite": "Complete Bipartite",
    "cycle": "Cycle",
    "path": "Path",
    "star": "Star",
    "wheel": "Wheel",
    "lollipop": "Lollipop",
    "barbell": "Barbell",
    "grid_2d": "2D Grid",
    "grid": "Grid",
    "hypercube": "Hypercube",
    "ladder": "Ladder",
    "circular_ladder": "Circular Ladder",
    "trivial": "Trivial",
    "empty": "Empty",
    "gnp_random": "GNP Random",
    "dense_gnm_random": "Dense GNM Random",
    "gnm_random": "GNM Random",
    "random_regular": "Random Regular",
    "random_shell": "Random Shell",
    "random_powerlaw_tree": "Random Powerlaw Tree",
    "random_powerlaw_tree_sequence": "Random Powerlaw Tree Sequence",
    "random_geometric": "Random Geometric",
    "soft_random_geometric": "Soft Random Geometric",
    "random_lobster": "Random Lobster",
    "random_interval_graph": "Random Interval Graph",
    "random_tree": "Random Tree",
    "stochastic_block_model": "Stochastic Block Model",
    "powerlaw_cluster": "Powerlaw Cluster",
    "connected_watts_strogatz": "Connected Watts-Strogatz",
    "newman_watts_strogatz": "Newman-Watts-Strogatz",
}

GRAPH_TYPE_ALIASES: dict[str, str] = {
    "er": "er",
    "e-r": "er",
    "erdos-renyi": "er",
    "erdos renyi": "er",
    "erdos_renyi": "er",
    "erdosrenyi": "er",
    "erdős-renyi": "er",
    "ws": "ws",
    "watts-strogatz": "ws",
    "watts_strogatz": "ws",
    "ba": "ba",
    "barabasi-albert": "ba",
    "barabasi_albert": "ba",
    "barabási-albert": "ba",
    "ea": "extended_barabasi",
    "extended attachment": "extended_barabasi",
    "extended_attachment": "extended_barabasi",
    "extended_barabasi": "extended_barabasi",
    "extended barabasi": "extended_barabasi",
    "mesh": "ws",
}

_GRAPH_TYPE_PRIORITY: tuple[str, ...] = ("er", "ws", "ba", "extended_barabasi")


def graph_type_label(key: str) -> str:
    k = graph_type_canonical(key)
    return GRAPH_TYPE_LABELS.get(k, k.replace("_", " ").title())


def graph_type_canonical(raw: Any) -> str:
    """Map UI label, alias, or internal id to a GRAPH_TYPES key."""
    if raw is None:
        return GRAPH_TYPES[0]
    s = str(raw).strip()
    if not s:
        return GRAPH_TYPES[0]
    low = s.lower().replace("_", " ").replace("-", " ")
    compact = low.replace(" ", "")
    if compact in GRAPH_TYPE_ALIASES:
        return GRAPH_TYPE_ALIASES[compact]
    if low in GRAPH_TYPE_ALIASES:
        return GRAPH_TYPE_ALIASES[low]
    snake = low.replace(" ", "_")
    if snake in GRAPH_TYPES:
        return snake
    for gt in GRAPH_TYPES:
        if graph_type_label(gt).lower() == s.lower():
            return gt
    return snake if snake in GRAPH_TYPES else GRAPH_TYPES[0]


def export_topology_for_save(topology: dict[str, Any]) -> dict[str, Any]:
    """Export topology with human-readable graph type names for YAML/JSON save."""
    import copy

    out = copy.deepcopy(topology)
    if not isinstance(out, dict):
        return {}

    def _label_block(block: dict[str, Any]) -> dict[str, Any]:
        b = dict(block)
        if b.get("graph_type"):
            b["graph_type"] = graph_type_label(graph_type_canonical(b["graph_type"]))
        return b

    graphs = out.get("graphs")
    if isinstance(graphs, list):
        out["graphs"] = [_label_block(g) if isinstance(g, dict) else g for g in graphs]
    if out.get("graph_type"):
        out = _label_block(out)
    return out


def graph_type_display_values() -> tuple[str, ...]:
    """Combobox values: full names, common types first."""
    ordered: list[str] = []
    seen: set[str] = set()
    for k in _GRAPH_TYPE_PRIORITY:
        if k in GRAPH_TYPES and k not in seen:
            ordered.append(graph_type_label(k))
            seen.add(k)
    rest = sorted(
        (graph_type_label(k) for k in GRAPH_TYPES if k not in seen),
        key=str.lower,
    )
    ordered.extend(rest)
    return tuple(ordered)


SEED_GRAPH_TYPES = frozenset(
    {
        "er",
        "ba",
        "extended_barabasi",
        "ws",
        "gnp_random",
        "dense_gnm_random",
        "gnm_random",
        "random_regular",
        "random_shell",
        "random_powerlaw_tree",
        "random_powerlaw_tree_sequence",
        "random_geometric",
        "soft_random_geometric",
        "random_lobster",
        "random_interval_graph",
        "random_tree",
        "stochastic_block_model",
        "powerlaw_cluster",
        "connected_watts_strogatz",
        "newman_watts_strogatz",
    }
)

DIRECTED_GRAPH_TYPES = frozenset({"gnp_random", "gnm_random", "stochastic_block_model"})
SELFLOOPS_GRAPH_TYPES = frozenset({"stochastic_block_model"})
POSITION_GRAPH_TYPES = frozenset({"random_geometric", "soft_random_geometric"})


def _resolve_path(path_str: str, base: Path | None) -> Path:
    p = Path(path_str.strip())
    if p.is_absolute():
        return p
    if base is not None:
        return (base / p).resolve()
    return p.resolve()


def default_topology_graph_block() -> dict[str, Any]:
    return {
        "graph_type": GRAPH_TYPES[0],
        "global_seed": "0",
        "directed": False,
        "selfloops": False,
        "supply_pos": False,
        "sbm_mode": "single",
        "pos_path": "",
        "param_values": [],
        "validation_text": "Validation: —",
    }


# Ordered parameter keys per graph type (matches simulation_gui._populate_graph_fields).
TOPOLOGY_PARAM_KEYS: dict[str, tuple[str, ...]] = {
    "er": ("n", "p"),
    "ba": ("n", "m"),
    "extended_barabasi": ("n", "m", "p"),
    "ws": ("n", "k", "p"),
    "complete": ("n",),
    "cycle": ("n",),
    "path": ("n",),
    "star": ("n",),
    "wheel": ("n",),
    "ladder": ("n",),
    "circular_ladder": ("n",),
    "hypercube": ("dimension",),
    "complete_bipartite": ("m", "n"),
    "lollipop": ("m", "n"),
    "barbell": ("m1", "m2"),
    "grid_2d": ("m", "n"),
    "grid": ("dim_sizes",),
    "empty": ("n",),
    "gnp_random": ("n", "p"),
    "dense_gnm_random": ("n", "m"),
    "gnm_random": ("n", "m"),
    "random_regular": ("d", "n"),
    "random_shell": ("constructor",),
    "random_powerlaw_tree": ("n", "exponent", "tries"),
    "random_powerlaw_tree_sequence": ("n", "exponent", "tries"),
    "random_geometric": ("n", "radius", "dim"),
    "soft_random_geometric": ("n", "radius", "dim", "p"),
    "random_lobster": ("n", "p1", "p2"),
    "random_interval_graph": ("n",),
    "random_tree": ("n",),
    "stochastic_block_model": ("sizes", "p"),
    "powerlaw_cluster": ("n", "m", "p"),
    "connected_watts_strogatz": ("n", "k", "p"),
    "newman_watts_strogatz": ("n", "k", "p"),
}

PARAM_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "n": ("n", "num_nodes", "numNodes", "nodes", "size", "N", "node_count"),
    "p": ("p", "prob", "probability", "edge_prob", "edge_probability", "edgeProbability"),
    "m": ("m", "num_edges", "edges", "neighbor_count"),
    "k": ("k", "degree", "neighbor_count", "neighbors"),
    "dimension": ("dimension", "dim", "d"),
    "dim_sizes": ("dim_sizes", "dimensions", "dims"),
    "radius": ("radius", "r"),
    "constructor": ("constructor", "shell"),
    "sizes": ("sizes", "blocks", "block_sizes"),
}

ENV_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "random_seed": ("random_seed", "seed", "randomSeed", "global_seed"),
    "save_path": ("save_path", "savePath", "output_path", "output_dir", "save_directory", "results_path"),
    "save_name": ("save_name", "saveName", "output_name", "run_name", "experiment_name"),
    "agent_assignment_path": (
        "agent_assignment_path",
        "agent_path",
        "agent_file",
        "agents_path",
        "agents_file",
    ),
    "topology_assignment_path": (
        "topology_assignment_path",
        "topology_path",
        "topology_file",
        "graph_path",
        "graph_file",
    ),
}

COMM_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "latency_prob": (
        "latency_prob",
        "latency_probability",
        "latencyProbability",
        "p_latency",
        "latency_probablility",
    ),
    "dropout_prob": (
        "dropout_prob",
        "dropout_probability",
        "dropoutProbability",
        "p_dropout",
        "drop_prob",
        "drop_probability",
    ),
    "interruption_prob": (
        "interruption_prob",
        "interruption_probability",
        "interruptionProbability",
        "p_interrupt",
        "p_interruption",
        "interrupt_prob",
    ),
    "latency_min": ("latency_min", "latencyMin", "min_latency", "latency_minimum"),
    "latency_max": ("latency_max", "latencyMax", "max_latency", "latency_maximum"),
    "earliest_interruption": (
        "earliest_interruption",
        "earliestInterruption",
        "earliest_interrupt",
        "min_interruption",
    ),
    "latest_interruption": (
        "latest_interruption",
        "latestInterruption",
        "latest_interrupt",
        "max_interruption",
    ),
}


def _pick_alias(source: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for name in aliases:
        if name in source and source[name] is not None:
            return source[name]
    return None


def _graph_type_from_block(block: dict[str, Any]) -> str:
    raw = _pick_alias(block, ("graph_type", "generator", "type", "graphType", "topology_type"))
    return graph_type_canonical(raw)


def _flatten_topology_block(block: dict[str, Any]) -> dict[str, Any]:
    flat = dict(block)
    nested = block.get("parameters") or block.get("graph_parameters") or block.get("graph_params")
    if isinstance(nested, dict):
        flat.update(nested)
    return flat


def _value_for_topology_param(flat: dict[str, Any], key: str) -> Any:
    names = (key,) + PARAM_KEY_ALIASES.get(key, ())
    return _pick_alias(flat, names)


def extract_param_values_from_topology_block(block: dict[str, Any]) -> list[str]:
    """Build param_values list from param_values, params, or named keys (n, p, …)."""
    if isinstance(block.get("param_values"), list) and block["param_values"]:
        return [str(x) for x in block["param_values"]]
    if isinstance(block.get("params"), list) and block["params"]:
        return [str(x) for x in block["params"]]
    nested = block.get("parameters") or block.get("graph_parameters") or block.get("graph_params")
    if isinstance(nested, list) and nested:
        return [str(x) for x in nested]

    flat = _flatten_topology_block(block)
    gt = _graph_type_from_block(flat)
    order = TOPOLOGY_PARAM_KEYS.get(gt, ())
    if order:
        out = [str(v) if (v := _value_for_topology_param(flat, k)) is not None else "" for k in order]
        if any(str(x).strip() for x in out):
            return out

    # Last resort: common ER keys when graph type unknown or missing order.
    fallback = ("n", "p", "m", "k", "dimension", "radius")
    out = [str(v) if (v := _value_for_topology_param(flat, k)) is not None else "" for k in fallback]
    while out and not str(out[-1]).strip():
        out.pop()
    return out


def normalize_topology_graph_block(block: dict[str, Any]) -> dict[str, Any]:
    """Convert on-disk topology shapes into GUI graph block dict."""
    flat = _flatten_topology_block(block)
    b = default_topology_graph_block()
    b["graph_type"] = _graph_type_from_block(flat)
    seed = _pick_alias(flat, ("global_seed", "seed", "graph_seed", "random_seed"))
    if seed is not None:
        b["global_seed"] = str(seed)
    for flag in ("directed", "selfloops", "supply_pos"):
        if flag in flat:
            b[flag] = bool(flat[flag])
    if flat.get("sbm_mode") is not None:
        b["sbm_mode"] = str(flat["sbm_mode"])
    if flat.get("pos_path") is not None:
        b["pos_path"] = str(flat["pos_path"])
    if flat.get("validation_text") is not None:
        b["validation_text"] = str(flat["validation_text"])
    b["param_values"] = extract_param_values_from_topology_block(block)
    return b


def _normalize_range_rows(rows: Any) -> list[list[str]]:
    if not isinstance(rows, list):
        return [["", ""]]
    out: list[list[str]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append([str(row.get("start", row.get("from", ""))), str(row.get("end", row.get("to", "")))])
        elif isinstance(row, (list, tuple)):
            out.append([str(x) for x in (list(row) + ["", ""])[:2]])
    return out if out else [["", ""]]


def normalize_communication_card(raw: dict[str, Any], index: int = 1) -> dict[str, Any]:
    b = default_communication_card(index)
    b["title"] = str(_pick_alias(raw, ("title", "name", "id")) or b["title"])
    for gui_key, aliases in COMM_FIELD_ALIASES.items():
        val = _pick_alias(raw, aliases)
        if val is not None:
            b[gui_key] = str(val)
    ar = raw.get("assignment_ranges") or raw.get("assignment") or raw.get("ranges")
    if isinstance(ar, list):
        b["assignment_ranges"] = _normalize_range_rows(ar)
    return b


def normalize_group_policy_card(raw: dict[str, Any], index: int = 1) -> dict[str, Any]:
    b = default_group_policy_card(index)
    b["title"] = str(_pick_alias(raw, ("title", "name", "id")) or b["title"])
    ro = raw.get("rounds") or raw.get("round") or raw.get("round_ranges")
    ao = raw.get("assignment") or raw.get("assignments") or raw.get("assignment_ranges")
    if isinstance(ro, list):
        b["rounds"] = _normalize_range_rows(ro)
    if isinstance(ao, list):
        b["assignment"] = _normalize_range_rows(ao)
    return b


def _cards_from_payload_value(val: Any) -> Optional[list[dict[str, Any]]]:
    if isinstance(val, list):
        return [copy.deepcopy(x) for x in val if isinstance(x, dict)]
    if isinstance(val, dict):
        inner = val.get("cards") or val.get("items") or val.get("entries")
        if isinstance(inner, list):
            return [copy.deepcopy(x) for x in inner if isinstance(x, dict)]
        return [copy.deepcopy(val)]
    return None


def environment_from_configuration(config: dict[str, Any]) -> dict[str, str]:
    env = {k: "" for k in default_experiment_state("")["environment"]}
    sources: list[dict[str, Any]] = []
    nested = config.get("environment")
    if isinstance(nested, dict):
        sources.append(nested)
    sources.append(config)
    for src in sources:
        for gui_key, aliases in ENV_FIELD_ALIASES.items():
            val = _pick_alias(src, aliases)
            if val is not None and str(val).strip():
                env[gui_key] = str(val)
    return env


def default_communication_card(n: int = 1) -> dict[str, Any]:
    return {
        "title": f"Communication {n}",
        "latency_prob": "",
        "dropout_prob": "",
        "latency_min": "",
        "latency_max": "",
        "assignment_ranges": [["", ""]],
    }


def default_group_policy_card(n: int = 1) -> dict[str, Any]:
    return {
        "title": f"Group Policy {n}",
        "rounds": [["", ""]],
        "assignment": [["", ""]],
    }


def flatten_mapping_for_display(data: Any, *, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten nested dict/list structures into dotted paths for read-only UI rows."""
    rows: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, (dict, list)):
                rows.extend(flatten_mapping_for_display(value, prefix=path))
            else:
                rows.append((path, "" if value is None else str(value)))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            path = f"{prefix}[{i}]" if prefix else f"[{i}]"
            if isinstance(value, (dict, list)):
                rows.extend(flatten_mapping_for_display(value, prefix=path))
            else:
                rows.append((path, "" if value is None else str(value)))
    else:
        rows.append((prefix or "value", "" if data is None else str(data)))
    return rows


def default_experiment_state(name: str) -> dict[str, Any]:
    g0 = default_topology_graph_block()
    return {
        "name": name,
        "network_config": {},
        "environment": {
            "random_seed": "0",
            "save_path": "",
            "save_name": "",
            "agent_assignment_path": "",
            "topology_assignment_path": "",
        },
        "topology": {
            "graphs": [default_topology_graph_block()],
            "active_graph_index": 0,
            **g0,
        },
        "notes": "",
        "profiles": [default_profile_state(1)],
        "models": [default_model_state(1)],
        "data_assignment": {"training": [], "validation": []},
        "communication_cards": [default_communication_card(1)],
        "group_policy_cards": [default_group_policy_card(1)],
    }


def default_profile_state(n: int) -> dict[str, Any]:
    return {
        "title": f"Profile {n}",
        "description": "",
        "role": "dfl_server",
        "aggregation": "average",
        "wait_time": "0",
        "agg_min": "",
        "freshness_cap": "",
        "training_time": "",
        "does_train": True,
        "metrics": "",
        "neighbor_ratio": "",
        "epochs": "",
        "minibatches": "",
        "release_agent": "",
        "group_id": "",
        "is_sync": False,
        "checkpoint": False,
        "assignment_ranges": [["", ""]],
    }


def default_model_state(n: int) -> dict[str, Any]:
    return {
        "title": f"Model {n}",
        "description": "",
        "model_type": "",
        "optimizer": "",
        "lr": "",
        "momentum": "",
        "batch_size": "",
        "criterion": "",
        "assignment_ranges": [["", ""]],
    }


def _flatten_nested_profile(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    inner = item.get("profile")
    if isinstance(inner, dict):
        for k, v in inner.items():
            if k not in out or out.get(k) in (None, ""):
                out[k] = v
    return out


def _flatten_nested_model(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    inner = item.get("model")
    if isinstance(inner, dict):
        for k, v in inner.items():
            if k not in out or out.get(k) in (None, ""):
                out[k] = v
    return out


def _profiles_list_from_payload(data: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    if isinstance(data.get("profile_assignment"), list):
        src = data["profile_assignment"]
    elif isinstance(data.get("profiles"), list):
        src = data["profiles"]
    else:
        return None
    return [_flatten_nested_profile(x) for x in src if isinstance(x, dict)]


def _models_list_from_payload(data: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    if isinstance(data.get("model_assignment"), list):
        src = data["model_assignment"]
    elif isinstance(data.get("models"), list):
        src = data["models"]
    else:
        return None
    return [_flatten_nested_model(x) for x in src if isinstance(x, dict)]


def _data_assignment_from_payload(data: dict[str, Any]) -> Optional[dict[str, Any]]:
    if isinstance(data.get("data_assignment"), dict):
        return copy.deepcopy(data["data_assignment"])
    out: dict[str, Any] = {}
    if isinstance(data.get("training"), list):
        out["training"] = copy.deepcopy(data["training"])
    if isinstance(data.get("validation"), list):
        out["validation"] = copy.deepcopy(data["validation"])
    return out if out else None


def _communication_cards_from_payload(data: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    for key in (
        "communication_cards",
        "communication_assignment",
        "communication",
        "Communication Assignment",
        "communication_settings",
    ):
        cards = _cards_from_payload_value(data.get(key))
        if cards:
            return cards
    flat = {}
    for gui_key, aliases in COMM_FIELD_ALIASES.items():
        val = _pick_alias(data, aliases)
        if val is not None and str(val).strip():
            flat[gui_key] = val
    if flat:
        return [flat]
    return None


def _group_policy_cards_from_payload(data: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    for key in (
        "group_policy_cards",
        "group_policy_assignment",
        "group_policy",
        "group_policies",
        "Group Policy Assignment",
        "group_policy_settings",
    ):
        cards = _cards_from_payload_value(data.get(key))
        if cards:
            return cards
    flat: dict[str, Any] = {}
    for rk in ("rounds", "round", "round_ranges"):
        if isinstance(data.get(rk), list):
            flat["rounds"] = data[rk]
            break
    for ak in ("assignment", "assignments", "assignment_ranges"):
        if isinstance(data.get(ak), list):
            flat["assignment"] = data[ak]
            break
    if flat:
        return [flat]
    return None


def _file_kind_from_filename(name: str) -> Optional[str]:
    n = name.lower()
    if "experiment" in n:
        return "experiment"
    if "topology" in n:
        return "topology"
    if "agent" in n or "assignment" in n:
        return "agent"
    return None

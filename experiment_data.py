import copy
from matplotlib import Path
from typing import Any, Optional

GRAPH_TYPES = (
    "er",
    "ba",
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

SEED_GRAPH_TYPES = frozenset(
    {
        "er",
        "ba",
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


def default_communication_card(n: int = 1) -> dict[str, Any]:
    return {
        "title": f"Communication {n}",
        "latency_prob": "",
        "dropout_prob": "",
        "interruption_prob": "",
        "latency_min": "",
        "latency_max": "",
        "earliest_interruption": "",
        "latest_interruption": "",
        "assignment_ranges": [["", ""]],
    }


def default_group_policy_card(n: int = 1) -> dict[str, Any]:
    return {
        "title": f"Group Policy {n}",
        "rounds": [["", ""]],
        "assignment": [["", ""]],
    }


def default_experiment_state(name: str) -> dict[str, Any]:
    g0 = default_topology_graph_block()
    return {
        "name": name,
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


def _file_kind_from_filename(name: str) -> Optional[str]:
    n = name.lower()
    if "experiment" in n:
        return "experiment"
    if "topology" in n:
        return "topology"
    if "agent" in n or "assignment" in n:
        return "agent"
    return None

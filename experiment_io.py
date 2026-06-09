"""Read/write experiment folder files (YAML only)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_VENDOR = Path(__file__).resolve().parent / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    import yaml
except ImportError as e:
    raise ImportError(
        "PyYAML is required for experiment YAML support. Install with: pip install pyyaml"
    ) from e

EXPERIMENT_BASENAME = "experiment"
TOPOLOGY_BASENAME = "topology"
AGENT_BASENAME = "agent_assignment"
NETWORK_BASENAME = "network"

REQUIRED_EXPERIMENT_BASENAMES = (EXPERIMENT_BASENAME, TOPOLOGY_BASENAME, AGENT_BASENAME)

EXPERIMENT_YAML = f"{EXPERIMENT_BASENAME}.yaml"
TOPOLOGY_YAML = f"{TOPOLOGY_BASENAME}.yaml"
AGENT_YAML = f"{AGENT_BASENAME}.yaml"
NETWORK_YAML = f"{NETWORK_BASENAME}.yaml"


def _yaml_dump(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)


def write_yaml_file(path: Path, data: Any) -> None:
    path.write_text(_yaml_dump(data), encoding="utf-8")


def read_yaml_file(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path.name}:\n{e}") from e
    except OSError as e:
        raise ValueError(f"Could not read {path.name}:\n{e}") from e


def yaml_path(folder: Path, basename: str) -> Path:
    return folder.resolve() / f"{basename}.yaml"


def missing_required_files(folder: Path) -> list[str]:
    missing: list[str] = []
    for base in REQUIRED_EXPERIMENT_BASENAMES:
        if not yaml_path(folder, base).is_file():
            missing.append(f"{base}.yaml")
    return missing


def read_required_yaml(folder: Path, basename: str) -> Any:
    path = yaml_path(folder, basename)
    if not path.is_file():
        raise ValueError(f"Missing required file:\n\n{path.name}")
    return read_yaml_file(path)


def load_network_config(folder: Path) -> dict[str, Any] | None:
    path = yaml_path(folder, NETWORK_BASENAME)
    if not path.is_file():
        return None
    raw = read_yaml_file(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")
    return raw


def build_agent_payload(st: dict[str, Any]) -> dict[str, Any]:
    return {
        "profiles": st.get("profiles") or [],
        "models": st.get("models") or [],
        "data_assignment": st.get("data_assignment") or {"training": [], "validation": []},
    }


def build_experiment_payload(st: dict[str, Any], *, default_environment: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(st.get("name") or ""),
        "environment": st.get("environment") or default_environment,
        "notes": st.get("notes") or "",
        "communication_cards": st.get("communication_cards") or [],
        "group_policy_cards": st.get("group_policy_cards") or [],
    }


def write_experiment_files(
    exp_dir: Path,
    st: dict[str, Any],
    *,
    topology_export: dict[str, Any],
    default_environment: dict[str, Any],
) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    st_name = str(st.get("name") or exp_dir.name)
    write_yaml_file(exp_dir / TOPOLOGY_YAML, topology_export)
    write_yaml_file(exp_dir / AGENT_YAML, build_agent_payload(st))
    write_yaml_file(
        exp_dir / EXPERIMENT_YAML,
        build_experiment_payload(st, default_environment=default_environment),
    )


def write_run_results(
    exp_dir: Path,
    *,
    st: dict[str, Any],
    topology_export: dict[str, Any],
    default_environment: dict[str, Any],
    log_text: str,
    summary: dict[str, Any],
) -> None:
    write_experiment_files(
        exp_dir,
        st,
        topology_export=topology_export,
        default_environment=default_environment,
    )
    (exp_dir / "simulation_log.txt").write_text(log_text, encoding="utf-8")
    write_yaml_file(exp_dir / "run_summary.yaml", summary)

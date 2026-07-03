"""Load, validate, and save network.yaml for the simulation platform."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

from experiment_io import read_yaml_file, write_yaml_file
from path_resolution import resolve_stack_path

NETWORK_FILENAME = "network.yaml"

ModelLayer = dict[str, Any]
ModelEntry = tuple[str, list[ModelLayer]]
OptimizerEntry = tuple[str, dict[str, Any]]
CriteriaEntry = tuple[str, dict[str, Any]]


def default_network_document() -> dict[str, Any]:
    return {
        "layer_types": {
            "Conv2D": {"parameters": ["in_channels", "out_channels", "kernel_size", "stride"]},
            "ReLU": {"parameters": []},
            "MaxPool": {"parameters": ["kernel_size", "stride"]},
            "Flatten": {"parameters": ["start_dim"]},
            "Linear": {"parameters": ["in_features", "out_features"]},
        },
        "models": {},
        "optimizers": {},
        "criteria": {},
    }


def _dig(data: Any, path: tuple[str, ...]) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def resolve_network_path(
    path_str: str,
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    return resolve_stack_path(path_str, NETWORK_FILENAME, driver_file=driver_file)


def load_network_yaml(path: Path) -> dict[str, Any]:
    raw = read_yaml_file(path)
    if raw is None:
        return default_network_document()
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a mapping at the root.")

    merged = default_network_document()
    for key in ("layer_types", "models", "optimizers", "criteria"):
        if isinstance(raw.get(key), dict):
            merged[key] = copy.deepcopy(raw[key])

    for key, val in raw.items():
        if key not in merged:
            merged[key] = copy.deepcopy(val)

    merged["_source_path"] = str(path.resolve())
    return merged


def save_network_yaml(path: Path, document: dict[str, Any]) -> None:
    payload = copy.deepcopy(document)
    payload.pop("_source_path", None)
    write_yaml_file(path, payload)


def layer_type_names(document: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    lt = document.get("layer_types")
    if isinstance(lt, dict):
        names.update(str(k) for k in lt.keys())
    models = document.get("models")
    if isinstance(models, dict):
        for block in models.values():
            for layer in model_layers(block):
                t = layer.get("type")
                if t:
                    names.add(str(t))
    return sorted(names)


def layer_type_parameter_names(document: dict[str, Any], layer_type: str) -> list[str]:
    lt = document.get("layer_types")
    if isinstance(lt, dict) and layer_type in lt:
        spec = lt[layer_type]
        if isinstance(spec, dict):
            params = spec.get("parameters", spec.get("params", []))
            if isinstance(params, list):
                return [str(p) for p in params]
    return []


def model_layers(block: dict[str, Any]) -> list[ModelLayer]:
    if not isinstance(block, dict):
        return []
    if isinstance(block.get("layers"), list):
        return [copy.deepcopy(x) for x in block["layers"] if isinstance(x, dict)]
    arch = block.get("architecture")
    if isinstance(arch, dict) and isinstance(arch.get("layers"), list):
        return [copy.deepcopy(x) for x in arch["layers"] if isinstance(x, dict)]
    return []


def model_block_from_layers(layers: list[ModelLayer]) -> dict[str, Any]:
    return {"layers": copy.deepcopy(layers)}


def parse_scalar(text: str) -> Any:
    s = str(text).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return ast.literal_eval(s)
    except (SyntaxError, ValueError):
        pass
    try:
        if "." in s or "e" in low:
            return float(s)
        return int(s)
    except ValueError:
        return s


def format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def layer_params_from_gui(
    document: dict[str, Any],
    layer_type: str,
    param_text: dict[str, str],
    extra_text: dict[str, str],
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in layer_type_parameter_names(document, layer_type):
        raw = param_text.get(key, "")
        if str(raw).strip() != "":
            params[key] = parse_scalar(raw)
    for key, raw in extra_text.items():
        fk = str(key).strip()
        if not fk or str(raw).strip() == "":
            continue
        params[fk] = parse_scalar(raw)
    return params


def split_layer_params(
    document: dict[str, Any],
    layer_type: str,
    params: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    params = params if isinstance(params, dict) else {}
    known = set(layer_type_parameter_names(document, layer_type))
    known_vals = {k: params[k] for k in known if k in params}
    extra = {k: v for k, v in params.items() if k not in known}
    return known_vals, extra


def network_document_from_definitions(definitions_document: dict[str, Any] | None) -> dict[str, Any]:
    """Derive a network document (optimizers + criteria) from definitions models.

    Models — and the optimizers/criteria embedded in them — now live in
    definitions.yaml. The Network page is built from that single source of
    truth rather than a separate network.yaml. Optimizer/criteria entries are
    de-duplicated by their ``type`` so identical configs across models collapse
    into one card.
    """
    out = default_network_document()
    out["models"] = {}
    optimizers: dict[str, Any] = {}
    criteria: dict[str, Any] = {}

    models = _dig(definitions_document or {}, ("definitions", "models"))
    if isinstance(models, dict):
        for _model_name, block in models.items():
            if not isinstance(block, dict):
                continue
            opt = block.get("optimizer")
            if isinstance(opt, dict):
                opt_type = str(opt.get("type", "") or "").strip()
                name = opt_type or "optimizer"
                if name not in optimizers:
                    optimizers[name] = copy.deepcopy(opt)
            crit = block.get("criterion")
            if isinstance(crit, dict):
                crit_type = str(crit.get("type", "") or "").strip()
                name = crit_type or "criterion"
                if name not in criteria:
                    criteria[name] = copy.deepcopy(crit)

    out["optimizers"] = optimizers
    out["criteria"] = criteria
    return out


def gui_state_from_document(document: dict[str, Any]) -> dict[str, Any]:
    models: list[ModelEntry] = []
    raw_models = document.get("models")
    if isinstance(raw_models, dict):
        for name, block in raw_models.items():
            if isinstance(block, dict):
                models.append((str(name), model_layers(block)))

    optimizers: list[OptimizerEntry] = []
    raw_opt = document.get("optimizers")
    if isinstance(raw_opt, dict):
        for name, block in raw_opt.items():
            if isinstance(block, dict):
                optimizers.append((str(name), copy.deepcopy(block)))

    criteria: list[CriteriaEntry] = []
    raw_crit = document.get("criteria")
    if isinstance(raw_crit, dict):
        for name, block in raw_crit.items():
            if isinstance(block, dict):
                criteria.append((str(name), copy.deepcopy(block)))

    return {
        "models": models,
        "optimizers": optimizers,
        "criteria": criteria,
    }


def merge_gui_into_document(
    base: dict[str, Any],
    *,
    models: list[ModelEntry] | None = None,
    optimizers: list[OptimizerEntry],
    criteria: list[CriteriaEntry],
) -> dict[str, Any]:
    """Merge GUI state into a network document.

    Models are managed in definitions.yaml; pass ``models=None`` (the default)
    to preserve any legacy ``models`` block in the base document untouched.
    """
    out = copy.deepcopy(base) if isinstance(base, dict) else default_network_document()

    if models is not None:
        model_map: dict[str, Any] = {}
        for name, layers in models:
            nm = str(name).strip()
            if not nm:
                continue
            model_map[nm] = model_block_from_layers(layers)
        out["models"] = model_map

    opt_map: dict[str, Any] = {}
    for name, block in optimizers:
        nm = str(name).strip()
        if not nm:
            continue
        opt_map[nm] = copy.deepcopy(block)
    out["optimizers"] = opt_map

    crit_map: dict[str, Any] = {}
    for name, block in criteria:
        nm = str(name).strip()
        if not nm:
            continue
        crit_map[nm] = copy.deepcopy(block)
    out["criteria"] = crit_map

    return out


def default_new_model() -> ModelEntry:
    return (
        "model_new",
        [{"type": "Linear", "params": {"in_features": 784, "out_features": 10}}],
    )


def default_new_optimizer() -> OptimizerEntry:
    return ("optimizer_new", {"type": "SGD", "lr": 0.01, "params": {"momentum": 0.9}})


def default_new_criteria() -> CriteriaEntry:
    return ("criteria_new", {"type": "CrossEntropyLoss", "params": {}})


def default_new_layer(document: dict[str, Any]) -> ModelLayer:
    types = layer_type_names(document)
    lt = types[0] if types else "Linear"
    params: dict[str, Any] = {}
    for key in layer_type_parameter_names(document, lt):
        params[key] = 1 if key in {"in_features", "out_features", "in_channels", "out_channels"} else 0
    return {"type": lt, "params": params}


def _is_number(val: Any) -> bool:
    try:
        float(val)
        return True
    except (TypeError, ValueError):
        return False


def validate_network_state(
    *,
    models: list[ModelEntry] | None = None,
    optimizers: list[OptimizerEntry],
    criteria: list[CriteriaEntry],
) -> tuple[bool, list[str]]:
    """Validate network GUI state.

    Models are managed in definitions.yaml; ``models`` is only validated when
    explicitly provided (legacy callers).
    """
    errors: list[str] = []

    seen_models: set[str] = set()
    for name, layers in models or []:
        nm = str(name).strip()
        if not nm:
            errors.append("Model name cannot be empty.")
            continue
        if nm in seen_models:
            errors.append(f"Duplicate model name detected: {nm!r}.")
        seen_models.add(nm)
        if not layers:
            errors.append(f"Model {nm!r} must contain at least one layer.")
        for idx, layer in enumerate(layers, start=1):
            lt = str(layer.get("type", "")).strip()
            if not lt:
                errors.append(f"Model {nm!r}, layer {idx}: layer type is required.")
            params = layer.get("params")
            if isinstance(params, dict):
                for pk, pv in params.items():
                    if pv is None or str(pv).strip() == "":
                        continue
                    if isinstance(pv, (dict, list)):
                        continue
                    if not _is_number(pv) and not isinstance(pv, str):
                        errors.append(f"Model {nm!r}, layer {idx}: parameter {pk!r} must be a valid value.")

    seen_opt: set[str] = set()
    for name, block in optimizers:
        nm = str(name).strip()
        if not nm:
            errors.append("Optimizer name cannot be empty.")
            continue
        if nm in seen_opt:
            errors.append(f"Duplicate optimizer name detected: {nm!r}.")
        seen_opt.add(nm)
        otype = str(block.get("type", "")).strip()
        if not otype:
            errors.append(f"Optimizer {nm!r}: optimizer type is required.")
        lr = block.get("lr")
        if lr is not None and str(lr).strip() != "":
            try:
                lr_val = float(lr)
            except (TypeError, ValueError):
                errors.append(f"Optimizer {nm!r}: learning rate must be a valid number.")
            else:
                if lr_val <= 0:
                    errors.append(f"Optimizer {nm!r}: learning rate must be greater than zero.")

    seen_crit: set[str] = set()
    for name, block in criteria:
        nm = str(name).strip()
        if not nm:
            errors.append("Criteria name cannot be empty.")
            continue
        if nm in seen_crit:
            errors.append(f"Duplicate criteria name detected: {nm!r}.")
        seen_crit.add(nm)
        ctype = str(block.get("type", "")).strip()
        if not ctype:
            errors.append(f"Criteria {nm!r}: criteria type is required.")

    return (len(errors) == 0, errors)


def print_network_load_report(document: dict[str, Any], *, source: Path | str | None = None) -> None:
    src = f" ({source})" if source else ""
    state = gui_state_from_document(document)
    print(f"\n=== Network YAML structure{src} ===")
    print(f"  Layer types: {len(layer_type_names(document))}")
    if state["models"]:
        print(f"  Models: {len(state['models'])} (legacy; models are now managed in definitions.yaml)")
    print(f"  Optimizers: {len(state['optimizers'])}")
    print(f"  Criteria: {len(state['criteria'])}")
    print()

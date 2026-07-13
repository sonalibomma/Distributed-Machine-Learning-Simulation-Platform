"""
Shared validation helpers for experiment UI and run preflight.

In distributed ML configs, -1 commonly means unlimited / disabled / use default.
Valid numeric profile values: -1, 0, or any positive number.
Invalid: -2, -3, …, non-numeric, empty required fields.
"""
from __future__ import annotations

from typing import Any, Optional

SENTINEL_DISABLED = -1

# Confirmed in backend agent_assignment.json (aggregation_minimum, wait_time, freshness_cap).
PROFILE_SENTINEL_FIELDS: frozenset[str] = frozenset(
    {
        "wait_time",
        "agg_min",
        "freshness_cap",
    }
)

# Same sentinel semantics; allowed when backend may omit enforcement.
PROFILE_OPTIONAL_SENTINEL_FIELDS: frozenset[str] = frozenset(
    {
        "training_time",
        "neighbor_ratio",
        "release_agent",
        "group_id",
        "minibatches",
        "epochs",
    }
)

PROFILE_FIELD_LABELS: dict[str, str] = {
    "wait_time": "wait_time",
    "agg_min": "aggregation_min",
    "freshness_cap": "freshness_cap",
    "training_time": "training_time",
    "neighbor_ratio": "neighbor_ratio",
    "epochs": "epochs",
    "minibatches": "minibatches",
    "release_agent": "release_agent",
    "group_id": "group_id",
}


def _strip_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def parse_numeric(x: Any) -> Optional[float]:
    txt = _strip_str(x)
    if not txt:
        return None
    try:
        return float(txt)
    except (TypeError, ValueError):
        return None


def allows_sentinel(field_key: str) -> bool:
    return field_key in PROFILE_SENTINEL_FIELDS or field_key in PROFILE_OPTIONAL_SENTINEL_FIELDS


def is_valid_sentinel_or_nonneg(value: float, *, allow_sentinel: bool = True) -> bool:
    if allow_sentinel and value == SENTINEL_DISABLED:
        return True
    return value >= 0


def is_strictly_invalid_negative(value: float, *, allow_sentinel: bool = True) -> bool:
    """True when value is negative but not the allowed -1 sentinel."""
    if value >= 0:
        return False
    if allow_sentinel and value == SENTINEL_DISABLED:
        return False
    return True


def profile_field_error(profile_index: int, field_key: str, raw_value: Any) -> Optional[str]:
    """
    Return an error message if field_key value is invalid; None if OK or empty.
    Empty optional fields are always OK.
    """
    txt = _strip_str(raw_value)
    if not txt:
        return None
    fv = parse_numeric(txt)
    label = PROFILE_FIELD_LABELS.get(field_key, field_key)
    prefix = f"Profile {profile_index + 1}: {label}"
    if fv is None:
        return f"{prefix} must be numeric (got {txt!r})."
    allow = allows_sentinel(field_key)
    if is_strictly_invalid_negative(fv, allow_sentinel=allow):
        if allow:
            return f"{prefix} must be -1 (unlimited/disabled) or ≥ 0 (got {fv:g})."
        return f"{prefix} must be ≥ 0 (got {fv:g})."
    return None


def model_field_error(model_index: int, field_key: str, raw_value: Any, *, min_positive: bool = False) -> Optional[str]:
    txt = _strip_str(raw_value)
    if not txt:
        return None
    fv = parse_numeric(txt)
    prefix = f"Model {model_index + 1}: {field_key}"
    if fv is None:
        return f"{prefix} must be numeric (got {txt!r})."
    if min_positive:
        if fv != int(fv):
            return f"{prefix} must be an integer (got {txt!r})."
        if int(fv) < 1:
            return f"{prefix} must be ≥ 1 (got {txt!r})."
        return None
    if fv < 0:
        return f"{prefix} must be ≥ 0 (got {fv:g})."
    return None

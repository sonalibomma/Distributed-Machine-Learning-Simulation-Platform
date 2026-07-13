from __future__ import annotations

from typing import Any, Optional, Tuple


def _parse_float(s: Any) -> Optional[float]:
    try:
        return float(str(s).strip())
    except Exception:
        return None


def _parse_prob(s: Any) -> Optional[float]:
    v = _parse_float(s)
    if v is None:
        return None
    if 0.0 <= v <= 1.0:
        return v
    return None


def _range_pairs(rows: Any) -> list[tuple[Optional[float], Optional[float]]]:
    out: list[tuple[Optional[float], Optional[float]]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        a, b = _parse_float(row[0]), _parse_float(row[1])
        out.append((a, b))
    return out


def normalize_communication_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a copy of communication cards with parsed numeric fields where possible."""
    raw = state.get("communication_cards")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for i, c in enumerate(raw):
        if not isinstance(c, dict):
            continue
        item = dict(c)
        item["_index"] = i
        for k in ("latency_prob", "dropout_prob", "latency_min", "latency_max"):
            if k in item:
                item[f"_{k}_p"] = _parse_prob(item[k]) if "prob" in k else _parse_float(item[k])
        ar = item.get("assignment_ranges")
        item["_assignment_ranges_parsed"] = _range_pairs(ar)
        out.append(item)
    return out


def normalize_group_policy_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("group_policy_cards")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for i, c in enumerate(raw):
        if not isinstance(c, dict):
            continue
        item = dict(c)
        item["_index"] = i
        item["_rounds_parsed"] = _range_pairs(item.get("rounds"))
        item["_assignment_parsed"] = _range_pairs(item.get("assignment"))
        out.append(item)
    return out


def validate_run_policies(state: dict[str, Any]) -> Tuple[bool, list[str]]:
    """
    Non-fatal checks: malformed probabilities or inconsistent ranges.
    Returns (all_ok, warnings).
    """
    warnings: list[str] = []
    comm = state.get("communication_cards")
    if isinstance(comm, list):
        for i, c in enumerate(comm):
            if not isinstance(c, dict):
                warnings.append(f"Communication card {i + 1} is not an object; skipped.")
                continue
            for k in ("latency_prob", "dropout_prob"):
                if k not in c:
                    continue
                s = c[k]
                if not str(s).strip():
                    continue
                if _parse_prob(s) is None:
                    warnings.append(f"Communication card {i + 1}: {k} should be empty or a probability in [0, 1].")
            for k in ("latency_min", "latency_max"):
                if k not in c:
                    continue
                s = c[k]
                if not str(s).strip():
                    continue
                if _parse_float(s) is None:
                    warnings.append(f"Communication card {i + 1}: {k} should be empty or numeric.")

    gp = state.get("group_policy_cards")
    if isinstance(gp, list):
        for i, c in enumerate(gp):
            if not isinstance(c, dict):
                warnings.append(f"Group policy card {i + 1} is not an object; skipped.")
                continue
            for label, key in (("Rounds", "rounds"), ("Assignment", "assignment")):
                rows = c.get(key)
                if not isinstance(rows, list):
                    continue
                for ri, row in enumerate(rows):
                    if not isinstance(row, (list, tuple)) or len(row) < 2:
                        continue
                    a, b = _parse_float(row[0]), _parse_float(row[1])
                    if a is not None and b is not None and a > b:
                        warnings.append(
                            f"Group policy card {i + 1} {label} row {ri + 1}: start ({a}) > end ({b})."
                        )

    return (len(warnings) == 0, warnings)


def summarize_policies_for_run(state: dict[str, Any]) -> str:
    """One-line human summary for logs / UI."""
    nc = len(normalize_communication_cards(state))
    ng = len(normalize_group_policy_cards(state))
    parts = [f"{nc} communication card(s)", f"{ng} group policy card(s)"]
    if nc > 0:
        c0 = state.get("communication_cards")
        if isinstance(c0, list) and c0 and isinstance(c0[0], dict):
            d = c0[0]
            lp = _parse_prob(d.get("latency_prob"))
            dp = _parse_prob(d.get("dropout_prob"))
            bits = []
            if lp is not None:
                bits.append(f"latency P={lp:g}")
            if dp is not None:
                bits.append(f"dropout P={dp:g}")
            if bits:
                parts.append("first card: " + ", ".join(bits))
    if ng > 0:
        g0 = state.get("group_policy_cards")
        if isinstance(g0, list) and g0 and isinstance(g0[0], dict):
            rp = _range_pairs(g0[0].get("rounds"))
            if rp:
                parts.append(f"first card rounds ranges: {len(rp)}")
    return "; ".join(parts)


def suggested_round_size_from_state(state: dict[str, Any], *, default: int, nn: int) -> int:
    """
    Optional tighter round step count from first group-policy rounds range (if parseable).
    """
    gp = state.get("group_policy_cards")
    if not isinstance(gp, list) or not gp:
        return max(2, min(80, default))
    c0 = gp[0]
    if not isinstance(c0, dict):
        return max(2, min(80, default))
    rp = _range_pairs(c0.get("rounds"))
    for a, b in rp:
        if a is None or b is None:
            continue
        span = abs(b - a)
        if span <= 0:
            continue
        guess = int(span) + 1
        return max(2, min(80, max(4, guess)))
    return max(2, min(80, default))


def suggested_comm_log_interval_ms(state: dict[str, Any], *, base_ms: int = 200) -> int:
    """Scale animation interval slightly from first-card latency bounds (non-fatal)."""
    comm = state.get("communication_cards")
    if not isinstance(comm, list) or not comm:
        return base_ms
    c0 = comm[0]
    if not isinstance(c0, dict):
        return base_ms
    lo = _parse_float(c0.get("latency_min"))
    hi = _parse_float(c0.get("latency_max"))
    if lo is None and hi is None:
        return base_ms
    avg = 0.0
    n = 0
    if lo is not None:
        avg += lo
        n += 1
    if hi is not None:
        avg += hi
        n += 1
    if n == 0:
        return base_ms
    avg = avg / n
    # Map average latency (interpreted as abstract steps) to 120–450 ms
    scaled = int(base_ms + min(250, max(0, avg * 15)))
    return max(120, min(450, scaled))

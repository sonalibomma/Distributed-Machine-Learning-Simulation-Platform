from __future__ import annotations

from typing import Any, Optional, Tuple

from experiment_data import SEED_GRAPH_TYPES, graph_type_canonical, graph_type_label


def _sf(s: Any, default: float = 0.0) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


def _si(s: Any, default: int = 0) -> int:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return default


def _nonempty(s: Any) -> bool:
    return bool(str(s).strip())


def _fail(msg: str) -> Tuple[bool, str]:
    return False, f"Validation: {msg}"


def _ok(extra: str = "") -> Tuple[bool, str]:
    if extra:
        return True, f"Validation: OK — {extra}"
    return True, "Validation: OK — parameters look consistent."


def validate_ui_topology(topology: dict[str, Any]) -> Tuple[bool, str]:
    """
    Check graph_type, param_values, SBM mode, and seed where required.
    Returns (ok, message) suitable for the topology validation label.
    """
    gt = graph_type_canonical(topology.get("graph_type", ""))
    if not gt:
        return _fail("choose a graph type.")

    pv = [str(x) for x in (topology.get("param_values") or [])]
    sbm_mode = str(topology.get("sbm_mode", "single")).strip().lower()

    def need_len(n: int) -> Optional[str]:
        if len(pv) < n:
            return f"expected at least {n} parameter field(s) for {gt!r}, got {len(pv)}."
        return None

    def check_prob_index(i: int, label: str) -> Optional[str]:
        if i >= len(pv):
            return f"missing {label}."
        if not _nonempty(pv[i]):
            return f"{label} is empty."
        p = _sf(pv[i], -1.0)
        if not 0.0 <= p <= 1.0:
            return f"{label} must be in [0, 1], got {p!r}."
        return None

    def check_int_min(i: int, label: str, minimum: int = 1) -> Optional[str]:
        if i >= len(pv):
            return f"missing {label}."
        if not _nonempty(pv[i]):
            return f"{label} is empty."
        v = _si(pv[i], -10**9)
        if v < minimum:
            return f"{label} must be an integer ≥ {minimum}, got {v!r}."
        return None

    def check_float_pos(i: int, label: str) -> Optional[str]:
        if i >= len(pv):
            return f"missing {label}."
        if not _nonempty(pv[i]):
            return f"{label} is empty."
        v = _sf(pv[i], -1.0)
        if v <= 0.0:
            return f"{label} must be > 0, got {v!r}."
        return None

    # --- types with explicit rules ---
    if gt == "er":
        err = need_len(2) or check_int_min(0, "n", 1) or check_prob_index(1, "p")
        if err:
            return _fail(err)
    elif gt == "ba":
        err = need_len(2) or check_int_min(0, "n", 2) or check_int_min(1, "m", 1)
        if err:
            return _fail(err)
    elif gt == "extended_barabasi":
        err = (
            need_len(3)
            or check_int_min(0, "n", 2)
            or check_int_min(1, "m", 1)
            or check_prob_index(2, "p")
        )
        if err:
            return _fail(err)
    elif gt == "ws":
        err = need_len(3) or check_int_min(0, "n", 3) or check_int_min(1, "k", 2) or check_prob_index(2, "p")
        if err:
            return _fail(err)
    elif gt in {"complete", "cycle", "path", "star", "wheel", "ladder", "circular_ladder"}:
        err = need_len(1) or check_int_min(0, "n", 1)
        if err:
            return _fail(err)
        if gt == "cycle" and _si(pv[0], 0) < 3:
            return _fail("n must be ≥ 3 for a cycle.")
        if gt == "wheel" and _si(pv[0], 0) < 4:
            return _fail("n must be ≥ 4 for a wheel.")
    elif gt == "hypercube":
        err = need_len(1) or check_int_min(0, "dimension", 1)
        if err:
            return _fail(err)
        if _si(pv[0], 0) > 6:
            return _fail("hypercube dimension is very large in the UI (>6); reduce for preview.")
    elif gt == "complete_bipartite":
        err = need_len(2) or check_int_min(0, "m", 1) or check_int_min(1, "n", 1)
        if err:
            return _fail(err)
    elif gt == "lollipop":
        err = need_len(2) or check_int_min(0, "m", 1) or check_int_min(1, "n (path length)", 0)
        if err:
            return _fail(err)
    elif gt == "barbell":
        err = need_len(2) or check_int_min(0, "m1", 1) or check_int_min(1, "m2", 1)
        if err:
            return _fail(err)
    elif gt == "grid_2d":
        err = need_len(2) or check_int_min(0, "m", 1) or check_int_min(1, "n", 1)
        if err:
            return _fail(err)
    elif gt == "grid":
        err = need_len(1)
        if err:
            return _fail(err)
        if not _nonempty(pv[0]):
            return _fail("dim_sizes is empty.")
        parts = [p.strip() for p in pv[0].split(",") if p.strip()]
        if not parts:
            return _fail("dim_sizes must list at least one positive integer.")
        for p in parts:
            if _si(p, 0) < 1:
                return _fail(f"each dimension in dim_sizes must be ≥ 1 ({p!r}).")
    elif gt == "trivial":
        if any(_nonempty(x) for x in pv):
            return _fail("trivial graph should have no parameters (clear extra values).")
    elif gt == "empty":
        err = need_len(1) or check_int_min(0, "n", 0)
        if err:
            return _fail(err)
    elif gt == "gnp_random":
        err = need_len(2) or check_int_min(0, "n", 1) or check_prob_index(1, "p")
        if err:
            return _fail(err)
    elif gt in {"dense_gnm_random", "gnm_random"}:
        err = need_len(2) or check_int_min(0, "n", 1) or check_int_min(1, "m", 0)
        if err:
            return _fail(err)
    elif gt == "random_regular":
        err = need_len(2) or check_int_min(0, "d", 1) or check_int_min(1, "n", 2)
        if err:
            return _fail(err)
    elif gt == "random_shell":
        err = need_len(1)
        if err:
            return _fail(err)
        if not _nonempty(pv[0]):
            return _fail("constructor string is empty.")
    elif gt in {"random_powerlaw_tree", "random_powerlaw_tree_sequence"}:
        err = need_len(3) or check_int_min(0, "n", 1)
        if err:
            return _fail(err)
        if _nonempty(pv[1]) and _sf(pv[1], 0) <= 0:
            return _fail("exponent must be positive.")
        if _nonempty(pv[2]) and _si(pv[2], 0) < 1:
            return _fail("tries must be ≥ 1.")
    elif gt == "random_geometric":
        err = need_len(3) or check_int_min(0, "n", 1) or check_float_pos(1, "radius") or check_int_min(2, "dim", 1)
        if err:
            return _fail(err)
    elif gt == "soft_random_geometric":
        err = need_len(4) or check_int_min(0, "n", 1) or check_float_pos(1, "radius") or check_int_min(2, "dim", 1)
        if err:
            return _fail(err)
        if _nonempty(pv[3]) and not (0.0 <= _sf(pv[3], -1) <= 1.0):
            return _fail("soft p must be in [0, 1].")
    elif gt == "random_lobster":
        err = need_len(3) or check_int_min(0, "n", 1) or check_prob_index(1, "p1") or check_prob_index(2, "p2")
        if err:
            return _fail(err)
    elif gt in {"random_interval_graph", "random_tree"}:
        err = need_len(1) or check_int_min(0, "n", 1)
        if err:
            return _fail(err)
    elif gt == "stochastic_block_model":
        err = need_len(2)
        if err:
            return _fail(err)
        if not _nonempty(pv[0]):
            return _fail("block sizes are empty.")
        sizes = [x.strip() for x in pv[0].split(",") if x.strip()]
        if not sizes:
            return _fail("block sizes must be comma-separated integers.")
        for s in sizes:
            if _si(s, 0) < 1:
                return _fail(f"each block size must be ≥ 1 ({s!r}).")
        if sbm_mode == "matrix":
            text = pv[1].strip()
            if not text:
                return _fail("p matrix is empty.")
            rows = [ln.split() for ln in text.replace(",", " ").splitlines() if ln.strip()]
            if not rows:
                return _fail("p matrix has no rows.")
            width = len(rows[0])
            if width == 0:
                return _fail("p matrix row is empty.")
            for r in rows:
                if len(r) != width:
                    return _fail("p matrix rows must have the same length.")
                for x in r:
                    try:
                        v = float(x)
                    except Exception:
                        return _fail(f"p matrix entry is not numeric ({x!r}).")
                    if not 0.0 <= v <= 1.0:
                        return _fail(f"p matrix entries must be in [0, 1] ({v}).")
            if len(rows) != len(sizes):
                return _fail("p matrix order should match number of blocks.")
        else:
            if not _nonempty(pv[1]):
                return _fail("scalar p is empty.")
            p = _sf(pv[1], -1.0)
            if not 0.0 <= p <= 1.0:
                return _fail(f"scalar p must be in [0, 1], got {p!r}.")
    elif gt == "powerlaw_cluster":
        err = need_len(3) or check_int_min(0, "n", 1) or check_int_min(1, "m", 1) or check_prob_index(2, "p")
        if err:
            return _fail(err)
    elif gt in {"connected_watts_strogatz", "newman_watts_strogatz"}:
        err = need_len(4) or check_int_min(0, "n", 3) or check_int_min(1, "k", 2) or check_prob_index(2, "p")
        if err:
            return _fail(err)
        if _nonempty(pv[3]) and _si(pv[3], 0) < 1:
            return _fail("tries must be ≥ 1.")
    else:
        # Generic / unknown: require every provided value to parse as number if non-empty
        for i, s in enumerate(pv):
            if not _nonempty(s):
                return _fail(f"empty value at field {i + 1} (fill or switch graph type).")
            try:
                float(str(s).strip())
            except Exception:
                return _fail(f"field {i + 1} is not numeric ({s!r}).")

    # Seed graphs: global_seed should be parseable
    if gt in SEED_GRAPH_TYPES:
        gs = topology.get("global_seed", "0")
        try:
            int(float(str(gs).strip()))
        except Exception:
            return _fail("global seed must be an integer (or decimal that maps to an integer).")

    return _ok(f"{graph_type_label(gt)} parameters checked.")

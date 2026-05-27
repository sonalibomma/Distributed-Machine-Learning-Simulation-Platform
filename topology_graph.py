from __future__ import annotations

import json
from matplotlib import Path
from typing import Any, Optional, Tuple

import networkx as nx


def _safe_int(s: Any, default: int = 0) -> int:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return default


def _safe_float(s: Any, default: float = 0.0) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


def graph_from_topology_dict(d: dict[str, Any]) -> Optional[nx.Graph]:
    """Parse common on-disk topology JSON shapes into a graph."""
    if not isinstance(d, dict):
        return None

    if "links" in d and "nodes" in d:
        try:
            G = nx.node_link_graph(d)
            if G.number_of_nodes() > 0:
                return G if not G.is_directed() else G.to_undirected()
        except Exception:
            pass

    inner = d.get("topology")
    if isinstance(inner, dict):
        g2 = graph_from_topology_dict(inner)
        if g2 is not None:
            return g2

    edges = d.get("edges") or d.get("edge_list")
    if isinstance(edges, list) and edges:
        G = nx.Graph()
        for e in edges:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                try:
                    G.add_edge(int(e[0]), int(e[1]))
                except Exception:
                    continue
        if G.number_of_edges() > 0 or G.number_of_nodes() > 0:
            return G

    adj = d.get("adjacency") or d.get("adjacency_matrix")
    if isinstance(adj, list) and adj:
        G = nx.Graph()
        for i, row in enumerate(adj):
            if not isinstance(row, (list, tuple)):
                continue
            for j, v in enumerate(row):
                try:
                    w = float(v)
                except Exception:
                    continue
                if w != 0 and i <= j:
                    G.add_edge(i, j)
        if G.number_of_nodes() > 0:
            return G

    return None


def _graph_type_from_dict(d: dict[str, Any]) -> str:
    g = d.get("graph_type") or d.get("generator") or ""
    return str(g).strip().lower()


def generate_from_ui_topology(topology: dict[str, Any]) -> Tuple[nx.Graph, str]:
    """Generate a graph from UI topology state (graph_type + param_values + seed)."""
    gt = str(topology.get("graph_type", "er")).strip().lower()
    pv = [str(x) for x in (topology.get("param_values") or [])]
    seed = _safe_int(topology.get("global_seed", 0), 0)

    def ri(i: int, default: int = 1) -> int:
        return _safe_int(pv[i], default) if i < len(pv) else default

    def rf(i: int, default: float = 0.1) -> float:
        return _safe_float(pv[i], default) if i < len(pv) else default

    try:
        if gt == "er":
            n, p = max(1, ri(0, 10)), min(1.0, max(0.0, rf(1, 0.2)))
            return nx.erdos_renyi_graph(n, p, seed=seed), f"erdos_renyi_graph(n={n}, p={p})"
        if gt == "ba":
            n, m = max(2, ri(0, 15)), max(1, ri(1, 2))
            m = min(m, n - 1)
            return nx.barabasi_albert_graph(n, m, seed=seed), f"barabasi_albert_graph(n={n}, m={m})"
        if gt == "ws":
            n, k, p = max(3, ri(0, 20)), max(2, ri(1, 4)), min(1.0, max(0.0, rf(2, 0.1)))
            if k >= n:
                k = n - 1
            return nx.watts_strogatz_graph(n, k, p, seed=seed), "watts_strogatz"
        if gt == "complete":
            n = max(1, ri(0, 8))
            return nx.complete_graph(n), f"complete_graph({n})"
        if gt == "path":
            n = max(1, ri(0, 15))
            return nx.path_graph(n), f"path_graph({n})"
        if gt == "cycle":
            n = max(3, ri(0, 15))
            return nx.cycle_graph(n), f"cycle_graph({n})"
        if gt == "star":
            n = max(1, ri(0, 10))
            return nx.star_graph(n), f"star_graph({n})"
        if gt == "wheel":
            n = max(4, ri(0, 10))
            return nx.wheel_graph(n), f"wheel_graph({n})"
        if gt == "empty":
            n = max(0, ri(0, 5))
            return nx.empty_graph(n), f"empty_graph({n})"
        if gt == "gnp_random":
            n, p = max(1, ri(0, 15)), min(1.0, max(0.0, rf(1, 0.2)))
            return nx.gnp_random_graph(n, p, seed=seed, directed=False), "gnp_random_graph"
        if gt in {"gnm_random", "dense_gnm_random"}:
            n = max(1, ri(0, 15))
            mmax = n * (n - 1) // 2
            m = max(0, min(mmax, ri(1, min(20, mmax))))
            return nx.gnm_random_graph(n, m, seed=seed), "gnm_random_graph"
        if gt == "random_regular":
            d, n = max(1, ri(0, 3)), max(d + 1, ri(1, 10))
            if n * d % 2 != 0:
                n += 1
            try:
                return nx.random_regular_graph(d, n, seed=seed), "random_regular_graph"
            except Exception:
                return nx.cycle_graph(max(3, n)), "random_regular_graph (fallback cycle)"
        if gt == "grid_2d":
            m, n = max(1, ri(0, 4)), max(1, ri(1, 4))
            return nx.grid_2d_graph(m, n), "grid_2d_graph"
        if gt == "lollipop":
            m, n = max(1, ri(0, 5)), max(0, ri(1, 3))
            return nx.lollipop_graph(m, n), "lollipop_graph"
        if gt == "barbell":
            m1, m2 = max(1, ri(0, 4)), max(1, ri(1, 4))
            return nx.barbell_graph(m1, m2), "barbell_graph"
        if gt == "complete_bipartite":
            na, nb = max(1, ri(0, 3)), max(1, ri(1, 3))
            return nx.complete_bipartite_graph(na, nb), "complete_bipartite_graph"
        if gt == "hypercube":
            dim = max(1, min(6, ri(0, 3)))
            return nx.hypercube_graph(dim), "hypercube_graph"
        if gt == "trivial":
            return nx.trivial_graph(), "trivial_graph"
    except Exception as e:
        return nx.path_graph(4), f"generation error ({e}); fallback path_graph(4)"

    # Fallback: try NetworkX function by name
    fn = getattr(nx, f"{gt}_graph", None)
    if callable(fn):
        try:
            G = fn(5)
            if isinstance(G, nx.Graph):
                return G, f"nx.{gt}_graph (generic)"
        except Exception:
            pass

    return nx.path_graph(5), f"unsupported type {gt!r}; using path_graph(5)"


def effective_topology_for_run(state: dict[str, Any]) -> dict[str, Any]:
    """
    Merge topology with the active entry in ``graphs`` (and ``active_graph_index``).
    Flat keys on ``topology`` mirror the active graph when exported from the UI.
    """
    topo = dict(state.get("topology") or {})
    graphs = topo.get("graphs")
    if isinstance(graphs, list) and graphs:
        try:
            idx = int(topo.get("active_graph_index", 0))
        except (TypeError, ValueError):
            idx = 0
        idx = max(0, min(idx, len(graphs) - 1))
        block = graphs[idx]
        if isinstance(block, dict):
            return {**topo, **block}
    return topo


def build_graph_for_run(state: dict[str, Any]) -> Tuple[nx.Graph, str]:
    """
    Prefer topology file when graph_type matches UI; otherwise generate from UI params.
    """
    topo = effective_topology_for_run(state)
    env = state.get("environment") or {}
    gt_ui = str(topo.get("graph_type", "er")).strip().lower()

    raw: Optional[dict[str, Any]] = None
    tpath = str(env.get("topology_assignment_path", "")).strip()
    if tpath:
        try:
            p = Path(tpath)
            if p.is_file():
                raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            raw = None

    if isinstance(raw, dict):
        gt_file = _graph_type_from_dict(raw)
        Gfile = graph_from_topology_dict(raw)
        if Gfile is not None and (Gfile.number_of_nodes() > 0 or Gfile.number_of_edges() > 0):
            if gt_file and gt_ui and gt_file == gt_ui:
                return Gfile, "topology file (graph_type matches UI)"
            if not gt_file:
                return Gfile, "topology file (no graph_type; using structure)"

    G, msg = generate_from_ui_topology(topo)
    return G, f"generated from UI — {msg}"


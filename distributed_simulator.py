from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Optional

import networkx as nx

from experiment_runtime import suggested_round_size_from_state


def _pf(s: Any) -> Optional[float]:
    try:
        v = float(str(s).strip())
        if 0.0 <= v <= 1.0:
            return v
    except Exception:
        pass
    return None


def _float(s: Any) -> Optional[float]:
    try:
        return float(str(s).strip())
    except Exception:
        return None


def _int_seed(state: dict[str, Any]) -> int:
    env = state.get("environment") or {}
    try:
        return int(float(str(env.get("random_seed", "0")).strip()))
    except Exception:
        return 0


@dataclass
class PendingMessage:
    uid: int
    src: int
    dst: int
    payload: float
    deliver_at: int


@dataclass
class StepResult:
    t: int
    round: int
    step_in_round: int
    round_length: int
    line: str
    event: str = "idle"
    initiator_idx: Optional[int] = None
    sender_idx: Optional[int] = None
    receiver_idx: Optional[int] = None
    delivery_src: Optional[int] = None
    delivery_dst: Optional[int] = None
    edge_highlight: Optional[tuple[int, int]] = None
    latency_steps: Optional[int] = None
    delivered: bool = False
    dropped: bool = False
    interrupted: int = 0
    aggregated: bool = False


@dataclass
class CommParams:
    p_drop: float = 0.0
    p_latency_event: float = 0.0
    p_interrupt: float = 0.0
    latency_min: Optional[float] = None
    latency_max: Optional[float] = None
    earliest_interrupt: Optional[float] = None
    latest_interrupt: Optional[float] = None


def _comm_from_state(state: dict[str, Any]) -> CommParams:
    raw = state.get("communication_cards")
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return CommParams()
    c = raw[0]
    lo = _float(c.get("latency_min"))
    hi = _float(c.get("latency_max"))
    ei = _float(c.get("earliest_interruption"))
    li = _float(c.get("latest_interruption"))
    return CommParams(
        p_drop=_pf(c.get("dropout_prob")) or 0.0,
        p_latency_event=_pf(c.get("latency_prob")) or 0.0,
        p_interrupt=_pf(c.get("interruption_prob")) or 0.0,
        latency_min=lo,
        latency_max=hi,
        earliest_interrupt=ei,
        latest_interrupt=li,
    )


def _lr_for_model(model: dict[str, Any]) -> Optional[float]:
    v = _float(model.get("lr"))
    if v is not None and v > 0:
        return min(1.0, v)
    return None


def _lr_from_models(state: dict[str, Any]) -> float:
    models = state.get("models")
    if isinstance(models, list) and models and isinstance(models[0], dict):
        v = _lr_for_model(models[0])
        if v is not None and v > 0:
            return min(1.0, v)
    return 0.3


def _all_ranges_empty(ar: Any) -> bool:
    if not isinstance(ar, list) or not ar:
        return True
    for row in ar:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            if str(row[0]).strip() != "" or str(row[1]).strip() != "":
                return False
    return True


def node_in_ranges(node_idx: int, ar: Any) -> bool:
    if not isinstance(ar, list):
        return False
    for row in ar:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        if str(row[0]).strip() == "" and str(row[1]).strip() == "":
            continue
        try:
            a = float(str(row[0]).strip())
            b = float(str(row[1]).strip())
        except Exception:
            continue
        lo, hi = int(round(a)), int(round(b))
        if lo > hi:
            lo, hi = hi, lo
        if lo <= node_idx <= hi:
            return True
    return False


def nodes_matching_entry(ent: dict[str, Any], n: int) -> set[int]:
    ar = ent.get("assignment_ranges")
    if not isinstance(ar, list):
        return set(range(n))
    if _all_ranges_empty(ar):
        return set(range(n))
    return {i for i in range(n) if node_in_ranges(i, ar)}


def assign_indices_from_ranges(n: int, items: list[dict[str, Any]]) -> list[int]:
    """Map each node index to an item index using assignment_ranges (first explicit match wins)."""
    if n <= 0:
        return []
    if not items:
        return [0] * n
    out: list[int] = []
    for i in range(n):
        chosen: Optional[int] = None
        for j, p in enumerate(items):
            ar = p.get("assignment_ranges") if isinstance(p, dict) else None
            if not isinstance(ar, list):
                ar = []
            if _all_ranges_empty(ar):
                continue
            if node_in_ranges(i, ar):
                chosen = j
                break
        if chosen is None:
            for j, p in enumerate(items):
                if not isinstance(p, dict):
                    continue
                ar = p.get("assignment_ranges")
                if isinstance(ar, list) and _all_ranges_empty(ar):
                    chosen = j
                    break
        out.append(chosen if chosen is not None else 0)
    return out


def _sampling_row_covers_node(row: Any, node_idx: int) -> bool:
    if not isinstance(row, (list, tuple)) or len(row) < 2:
        return False
    if str(row[0]).strip() == "" and str(row[1]).strip() == "":
        return False
    try:
        a = float(str(row[0]).strip())
        b = float(str(row[1]).strip())
    except Exception:
        return False
    lo, hi = int(round(a)), int(round(b))
    if lo > hi:
        lo, hi = hi, lo
    return lo <= node_idx <= hi


def _sampling_row_weight(row: Any) -> float:
    if not isinstance(row, (list, tuple)) or len(row) < 3:
        return 1.0
    w = _float(row[2])
    if w is None or w < 0:
        return 1.0
    return float(w)


def compute_shard_weights(n: int, data_assignment: Optional[dict[str, Any]]) -> list[float]:
    """
    Per-node data shard weights from sampling triplets (training entries first, then validation).
    """
    if n <= 0:
        return []
    out = [1.0] * n
    if not data_assignment or not isinstance(data_assignment, dict):
        return out
    train_list = data_assignment.get("training")
    val_list = data_assignment.get("validation")
    if not isinstance(train_list, list):
        train_list = []
    if not isinstance(val_list, list):
        val_list = []

    for i in range(n):
        w: Optional[float] = None
        for ent in train_list:
            if not isinstance(ent, dict):
                continue
            samp = ent.get("sampling")
            if not isinstance(samp, list):
                continue
            for row in samp:
                if _sampling_row_covers_node(row, i):
                    w = _sampling_row_weight(row)
                    break
            if w is not None:
                break
        if w is None:
            for ent in val_list:
                if not isinstance(ent, dict):
                    continue
                samp = ent.get("sampling")
                if not isinstance(samp, list):
                    continue
                for row in samp:
                    if _sampling_row_covers_node(row, i):
                        w = _sampling_row_weight(row)
                        break
                if w is not None:
                    break
        out[i] = w if w is not None else 1.0
    return out


def _profile_wait_steps(prof: dict[str, Any]) -> int:
    try:
        v = int(float(str(prof.get("wait_time", "0")).strip()))
        if v < 0:
            return 0
        return v
    except Exception:
        return 0


def compute_can_train(n: int, data_assignment: Optional[dict[str, Any]]) -> list[bool]:
    """
    Nodes marked validation-only (via data_assignment) do not receive local SGD-style updates.
    """
    if n <= 0:
        return []
    if not data_assignment or not isinstance(data_assignment, dict):
        return [True] * n
    train_list = data_assignment.get("training")
    val_list = data_assignment.get("validation")
    if not isinstance(train_list, list):
        train_list = []
    if not isinstance(val_list, list):
        val_list = []

    if not train_list and not val_list:
        return [True] * n

    train_u: set[int] = set()
    for ent in train_list:
        if isinstance(ent, dict):
            train_u |= nodes_matching_entry(ent, n)

    val_u: set[int] = set()
    for ent in val_list:
        if isinstance(ent, dict):
            val_u |= nodes_matching_entry(ent, n)

    if train_u:
        return [i in train_u for i in range(n)]

    if val_u:
        return [i not in val_u for i in range(n)]

    return [True] * n


def _mix_alpha(prof: dict[str, Any], model: dict[str, Any], lr_default: float) -> float:
    mode = str(prof.get("aggregation", "average")).lower()
    lr = _lr_for_model(model)
    if lr is None or lr <= 0:
        lr = lr_default
    lr = min(1.0, max(0.0, lr))
    if mode == "weighted_average":
        nr = _float(prof.get("neighbor_ratio"))
        if nr is not None and 0.0 <= nr <= 1.0:
            return nr
    return lr


class DistributedSimulator:
    """
    One logical agent per graph vertex. Each global step:
    - interrupts in-flight messages (stochastic),
    - delivers messages due at this tick,
    - one initiator vertex attempts one gossip message to a random neighbor,
    - optional end-of-round federated aggregation.
    """

    def __init__(
        self,
        G: nx.Graph,
        experiment_state: dict[str, Any],
        *,
        node_list: list[Any],
        node_to_idx: dict[Any, int],
        round_length: int,
    ):
        self.G = G
        self.state = experiment_state
        self.node_list = list(node_list)
        self.node_to_idx = dict(node_to_idx)
        self.n = len(self.node_list)
        self.round_length = max(2, min(200, round_length))
        self.idx_to_node = {self.node_to_idx[n]: n for n in self.node_list}

        seed = (_int_seed(experiment_state) + self.n * 17) & 0x7FFFFFFF
        self.rng = random.Random(seed)
        self.comm = _comm_from_state(experiment_state)
        self.lr_default = _lr_from_models(experiment_state)

        raw_pf = experiment_state.get("profiles")
        self.profiles = [p for p in (raw_pf if isinstance(raw_pf, list) else []) if isinstance(p, dict)]
        if not self.profiles:
            self.profiles = [{}]
        raw_md = experiment_state.get("models")
        self.models = [m for m in (raw_md if isinstance(raw_md, list) else []) if isinstance(m, dict)]
        if not self.models:
            self.models = [{}]

        self.profile_idx = assign_indices_from_ranges(self.n, self.profiles)
        self.model_idx = assign_indices_from_ranges(self.n, self.models)
        self.can_train = compute_can_train(self.n, experiment_state.get("data_assignment"))
        self.shard_w = compute_shard_weights(self.n, experiment_state.get("data_assignment"))

        self.values = [self.rng.random() for _ in range(self.n)]
        self.pending: list[PendingMessage] = []
        self._next_uid = 1
        self.t = 0
        self._neighbor_rr: dict[int, int] = {}
        self._last_send_tick: list[int] = [-1] * self.n

    @classmethod
    def from_experiment(
        cls,
        G: nx.Graph,
        experiment_state: dict[str, Any],
        node_list: list[Any],
        node_to_idx: dict[Any, int],
    ) -> "DistributedSimulator":
        nn = max(len(node_list), 1)
        default_rs = max(8, min(20, nn + 4))
        rl = suggested_round_size_from_state(
            experiment_state, default=default_rs, nn=nn
        )
        return cls(G, experiment_state, node_list=node_list, node_to_idx=node_to_idx, round_length=rl)

    def _delay_steps(self) -> int:
        """Integer delay until delivery (>=0)."""
        lo, hi = self.comm.latency_min, self.comm.latency_max
        if lo is not None and hi is not None:
            a, b = int(round(lo)), int(round(hi))
            if b < a:
                a, b = b, a
            return self.rng.randint(max(0, a), max(a, b))
        if self.rng.random() < self.comm.p_latency_event:
            return self.rng.randint(1, 3)
        return 0

    def _interrupt_allowed(self) -> bool:
        """Optional window for interruption (steps)."""
        ei, li = self.comm.earliest_interrupt, self.comm.latest_interrupt
        if ei is None and li is None:
            return True
        if ei is not None and self.t < ei:
            return False
        if li is not None and self.t > li:
            return False
        return True

    def _interrupt_phase(self) -> int:
        if self.comm.p_interrupt <= 0:
            return 0
        if not self._interrupt_allowed():
            return 0
        removed = 0
        still: list[PendingMessage] = []
        for m in self.pending:
            if m.deliver_at > self.t and self.rng.random() < self.comm.p_interrupt:
                removed += 1
            else:
                still.append(m)
        self.pending = still
        return removed

    def _apply_gossip_update(self, dst: int, payload: float) -> None:
        if not self.can_train[dst]:
            return
        pi = self.profile_idx[dst]
        prof = self.profiles[pi] if 0 <= pi < len(self.profiles) else {}
        if not bool(prof.get("does_train", True)):
            return
        mi = self.model_idx[dst]
        model = self.models[mi] if 0 <= mi < len(self.models) else {}
        a = _mix_alpha(prof, model, self.lr_default)
        mode = str(prof.get("aggregation", "average")).lower()
        old = self.values[dst]
        if mode == "sum":
            self.values[dst] = old + a * payload
        elif mode == "max":
            self.values[dst] = max(old, payload)
        else:
            self.values[dst] = (1.0 - a) * old + a * payload

    def _deliver_phase(self) -> tuple[int, Optional[tuple[int, int]]]:
        delivered = 0
        highlight: Optional[tuple[int, int]] = None
        remain: list[PendingMessage] = []
        for m in self.pending:
            if m.deliver_at == self.t:
                self._apply_gossip_update(m.dst, m.payload)
                delivered += 1
                highlight = (m.src, m.dst)
            else:
                remain.append(m)
        self.pending = remain
        return delivered, highlight

    def _pick_neighbor(self, src_idx: int) -> Optional[int]:
        u = self.idx_to_node[src_idx]
        nbrs = list(self.G.neighbors(u))
        if not nbrs:
            return None
        k = self._neighbor_rr.get(src_idx, 0)
        self._neighbor_rr[src_idx] = (k + 1) % len(nbrs)
        v = nbrs[k]
        return self.node_to_idx[v]

    def _attempt_send(self) -> tuple[bool, Optional[tuple[int, int]], str, Optional[int]]:
        """
        Returns (dropped, pair_or_none, tag, latency_steps).
        tag: scheduled | drop | cooldown | no_neighbor | empty
        """
        if self.n == 0:
            return False, None, "empty", None
        src = self.t % self.n
        pi = self.profile_idx[src]
        prof = self.profiles[pi] if 0 <= pi < len(self.profiles) else {}
        wait = _profile_wait_steps(prof)
        last = self._last_send_tick[src]
        if wait > 0 and last >= 0 and (self.t - last) < wait:
            return False, None, "cooldown", None

        dst = self._pick_neighbor(src)
        if dst is None:
            return False, None, "no_neighbor", None
        if self.rng.random() < self.comm.p_drop:
            return True, (src, dst), "drop", None
        delay = self._delay_steps()
        sw = self.shard_w[src] if 0 <= src < len(self.shard_w) else 1.0
        eff_payload = self.values[src] * sw
        self.pending.append(
            PendingMessage(
                uid=self._next_uid,
                src=src,
                dst=dst,
                payload=eff_payload,
                deliver_at=self.t + delay,
            )
        )
        self._next_uid += 1
        self._last_send_tick[src] = self.t
        return False, (src, dst), "scheduled", delay

    def _aggregate_round(self) -> None:
        """Weighted FedAvg over training nodes (shard_w); validation-only nodes unchanged."""
        if self.n == 0:
            return
        tw = 0.0
        acc = 0.0
        for i in range(self.n):
            if not self.can_train[i]:
                continue
            w = self.shard_w[i] if i < len(self.shard_w) else 1.0
            tw += w
            acc += w * self.values[i]
        if tw <= 0:
            return
        mu = acc / tw
        for i in range(self.n):
            if self.can_train[i]:
                self.values[i] = mu

    def step(self) -> StepResult:
        if self.n == 0:
            return StepResult(
                t=self.t,
                round=1,
                step_in_round=0,
                round_length=self.round_length,
                line="empty graph",
            )

        old_t = self.t
        initiator = old_t % self.n
        intr = self._interrupt_phase()
        delivered, d_high = self._deliver_phase()
        dropped, pair, send_tag, latency_steps = self._attempt_send()

        aggregated = False
        line_parts: list[str] = []
        if intr:
            line_parts.append(f"{intr} message(s) interrupted")
        if delivered and d_high:
            ds, dr = d_high
            line_parts.append(f"Agent {ds} → Agent {dr}: model update delivered")
        if send_tag == "cooldown":
            line_parts.append(f"Initiator {initiator}: wait_time cooldown")
        elif send_tag == "no_neighbor":
            line_parts.append(f"Initiator {initiator}: no neighbor")
        elif pair:
            s, r = pair
            if dropped:
                line_parts.append(f"Agent {s} → Agent {r}: transmission dropped")
            else:
                lat_note = f" (latency {latency_steps} step(s))" if latency_steps else " (immediate)"
                line_parts.append(f"Agent {s} → Agent {r}: model transmitted{lat_note}")
        if not line_parts:
            line_parts.append(f"Round tick — initiator {initiator}")

        self.t += 1
        if self.t > 0 and self.t % self.round_length == 0:
            self._aggregate_round()
            aggregated = True
            line_parts.append("Aggregation complete (federated mean)")

        line = "; ".join(line_parts)
        current_round = old_t // self.round_length + 1
        step_in_round = old_t % self.round_length + 1

        if aggregated:
            event = "aggregation"
        elif intr:
            event = "interruption"
        elif dropped and pair:
            event = "dropout"
        elif delivered and d_high:
            event = "delivery"
        elif send_tag == "scheduled" and pair:
            event = "transmission_started"
        elif send_tag == "cooldown":
            event = "cooldown"
        elif send_tag == "no_neighbor":
            event = "no_neighbor"
        else:
            event = "idle"

        if d_high:
            edge_highlight = d_high
        elif pair:
            edge_highlight = pair
        else:
            edge_highlight = None

        return StepResult(
            t=self.t,
            round=current_round,
            step_in_round=step_in_round,
            round_length=self.round_length,
            line=line,
            event=event,
            initiator_idx=initiator,
            sender_idx=pair[0] if pair else None,
            receiver_idx=pair[1] if pair else None,
            delivery_src=d_high[0] if delivered and d_high else None,
            delivery_dst=d_high[1] if delivered and d_high else None,
            edge_highlight=edge_highlight,
            latency_steps=latency_steps,
            delivered=delivered > 0,
            dropped=dropped,
            interrupted=intr,
            aggregated=aggregated,
        )


def total_simulation_frames(experiment_state: dict[str, Any], nn: int, *, rounds: int = 24) -> int:
    """Total animation frames == simulator steps (one step per frame)."""
    default_rs = max(8, min(20, nn + 4))
    rl = suggested_round_size_from_state(experiment_state, default=default_rs, nn=max(nn, 1))
    return min(4000, max(rl * rounds, rl * 8))

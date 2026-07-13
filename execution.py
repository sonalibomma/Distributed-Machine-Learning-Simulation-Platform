"""Execution command generation and local subprocess helpers."""

from __future__ import annotations

import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

EXECUTION_MODES: tuple[str, ...] = ("local", "remote")
EXECUTION_MODE_LABELS: dict[str, str] = {
    "local": "Local",
    "remote": "Remote (Slurm)",
}

EXECUTION_STATUSES: tuple[str, ...] = ("Idle", "Running", "Completed", "Failed", "Stopped")


@dataclass
class ExecutionContext:
    """Paths and mode collected from the main window at run time."""

    mode: str = "local"
    driver_path: Path | None = None
    permutations_path: Path | None = None
    topologies_path: Path | None = None
    assignments_path: Path | None = None
    definitions_path: Path | None = None
    network_path: Path | None = None
    experiment_folder: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        def _p(path: Path | None) -> str:
            return str(path) if path else ""

        return {
            "mode": self.mode,
            "driver_path": _p(self.driver_path),
            "permutations_path": _p(self.permutations_path),
            "topologies_path": _p(self.topologies_path),
            "assignments_path": _p(self.assignments_path),
            "definitions_path": _p(self.definitions_path),
            "network_path": _p(self.network_path),
            "experiment_folder": _p(self.experiment_folder),
        }


def normalize_execution_mode(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if s in ("remote", "slurm", "remote (slurm)"):
        return "remote"
    return "local"


def build_orchestrator_command(ctx: ExecutionContext) -> str:
    """
    Build Dylan's orchestrator command line (informational / future execution).

    Replace argv construction in ``resolve_run_command`` when the orchestrator module is wired.
    """
    parts: list[str] = ["python", "-m", "orchestrator"]
    flag_map = (
        ("--driver", ctx.driver_path),
        ("--permutations", ctx.permutations_path),
        ("--topologies", ctx.topologies_path),
        ("--assignments", ctx.assignments_path),
        ("--definitions", ctx.definitions_path),
        ("--network", ctx.network_path),
        ("--experiment", ctx.experiment_folder),
    )
    for flag, path in flag_map:
        if path is None:
            continue
        p = Path(path)
        if p.is_file() or p.is_dir():
            parts.extend([flag, str(p)])
    if ctx.mode == "remote":
        parts.append("--slurm")
    return " ".join(shlex.quote(part) for part in parts)


def resolve_run_command(ctx: ExecutionContext) -> tuple[list[str], str]:
    """
    Return ``(argv, display_command)``.

    ``display_command`` is the orchestrator command shown in the UI.
    ``argv`` is what we execute today (placeholder until orchestrator is available).
    """
    display = build_orchestrator_command(ctx)
    if ctx.mode == "remote":
        return ([], display)
    return (["echo", "Simulation Started"], display)


class LocalProcessRunner:
    """Run a subprocess locally and stream stdout/stderr to callbacks."""

    def __init__(
        self,
        argv: list[str],
        *,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
        on_finished: Callable[[int], None] | None = None,
    ) -> None:
        self.argv = list(argv)
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr
        self._on_finished = on_finished
        self._proc: subprocess.Popen[str] | None = None
        self._threads: list[threading.Thread] = []
        self._stopped = False

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if not self.argv:
            raise ValueError("No command to execute.")
        self._stopped = False
        self._proc = subprocess.Popen(
            self.argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _pump(stream, handler: Callable[[str], None] | None) -> None:
            if stream is None or handler is None:
                return
            for line in iter(stream.readline, ""):
                if self._stopped:
                    break
                handler(line.rstrip("\n"))
            stream.close()

        if self._proc.stdout is not None:
            t_out = threading.Thread(target=_pump, args=(self._proc.stdout, self._on_stdout), daemon=True)
            t_out.start()
            self._threads.append(t_out)
        if self._proc.stderr is not None:
            t_err = threading.Thread(target=_pump, args=(self._proc.stderr, self._on_stderr), daemon=True)
            t_err.start()
            self._threads.append(t_err)

        def _wait() -> None:
            code = self._proc.wait() if self._proc is not None else -1
            if self._on_finished is not None:
                self._on_finished(code)

        threading.Thread(target=_wait, daemon=True).start()

    def stop(self) -> None:
        self._stopped = True
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass

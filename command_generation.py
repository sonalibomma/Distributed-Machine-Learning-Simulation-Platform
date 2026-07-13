"""Generate orchestrator command previews from manifests and execution requests."""

from __future__ import annotations

import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from execution import ExecutionContext, build_orchestrator_command, normalize_execution_mode
from experiment_instance_builder import build_experiment_instances
from manifest_export import MANIFEST_INDEX_FILENAME, export_instance_manifests
from orchestrator_adapter import ExecutionRequest, OrchestratorAdapter, OrchestratorAdapterResult
from run_config_builder import (
    RunConfiguration,
    RunStackSnapshot,
    build_and_validate_run_configuration,
)


@dataclass
class CommandPreviewResult:
    """Outcome of preparing an orchestrator command preview (no execution)."""

    command: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    export_dir: Path | None = None
    run_configuration: RunConfiguration | None = None
    instance_count: int = 0
    execution_requests: list[ExecutionRequest] = field(default_factory=list)
    adapter_result: OrchestratorAdapterResult | None = None

    @property
    def valid(self) -> bool:
        return not self.errors and bool(self.command.strip())


def build_orchestrator_command_from_manifests(
    *,
    driver_path: Path | None,
    export_dir: Path,
    mode: str = "local",
    instance_manifest_path: Path | None = None,
) -> str:
    """
    Build a placeholder orchestrator CLI string for Dylan's orchestrator.

    Final flag names may change when the orchestrator module is wired.
    """
    parts: list[str] = ["python", "-m", "orchestrator"]

    if driver_path is not None:
        driver = Path(driver_path)
        if driver.is_file():
            parts.extend(["--driver", str(driver.resolve())])

    export_resolved = export_dir.resolve()
    index_path = export_resolved / MANIFEST_INDEX_FILENAME
    if index_path.is_file():
        parts.extend(["--manifest-index", str(index_path)])

    if export_resolved.is_dir():
        parts.extend(["--export-dir", str(export_resolved)])

    if instance_manifest_path is not None:
        inst = Path(instance_manifest_path)
        if inst.is_file():
            parts.extend(["--instance", str(inst.resolve())])

    if normalize_execution_mode(mode) == "remote":
        parts.append("--slurm")

    return " ".join(shlex.quote(part) for part in parts)


def build_orchestrator_command_from_requests(
    *,
    driver_path: Path | None,
    export_dir: Path,
    execution_requests: list[ExecutionRequest],
    mode: str = "local",
    active_instance_id: int | None = None,
) -> str:
    """Prefer manifest-index batch command; add --instance when a single active request is selected."""
    instance_path: Path | None = None
    if active_instance_id is not None:
        for req in execution_requests:
            if req.instance_id == active_instance_id:
                instance_path = req.manifest_path
                break
    elif len(execution_requests) == 1:
        instance_path = execution_requests[0].manifest_path

    return build_orchestrator_command_from_manifests(
        driver_path=driver_path,
        export_dir=export_dir,
        mode=mode,
        instance_manifest_path=instance_path,
    )


def prepare_command_preview(
    snapshot: RunStackSnapshot,
    *,
    mode: str = "local",
    export_dir: Path | None = None,
    driver_root: Path | None = None,
    active_instance_id: int | None = None,
    staging_parent: Path | None = None,
) -> CommandPreviewResult:
    """
    Validate configuration, build instances, load execution requests, and generate command.

    Does not invoke the orchestrator or launch subprocesses.
    """
    run_config, errors = build_and_validate_run_configuration(snapshot)
    if errors or run_config is None:
        return CommandPreviewResult("", errors)

    instances = build_experiment_instances(run_config)
    if not instances:
        return CommandPreviewResult("", ["No experiment instances could be built."])

    target_dir = export_dir
    if target_dir is None:
        parent = staging_parent or Path(tempfile.gettempdir())
        target_dir = Path(tempfile.mkdtemp(prefix="wireframe_manifests_", dir=str(parent)))

    try:
        export_instance_manifests(instances, target_dir)
    except OSError as e:
        return CommandPreviewResult("", [f"Could not write manifest files: {e}"])

    adapter = OrchestratorAdapter(target_dir, driver_root=driver_root)
    adapter_result = adapter.load()
    if adapter_result.errors:
        return CommandPreviewResult(
            "",
            adapter_result.errors,
            warnings=adapter_result.warnings,
            export_dir=target_dir,
            run_configuration=run_config,
            instance_count=len(instances),
            adapter_result=adapter_result,
        )

    driver_path = snapshot.driver_path
    selected_id = active_instance_id
    if selected_id is None and len(adapter_result.execution_requests) == 1:
        selected_id = adapter_result.execution_requests[0].instance_id

    command = build_orchestrator_command_from_requests(
        driver_path=driver_path,
        export_dir=target_dir,
        execution_requests=adapter_result.execution_requests,
        mode=mode,
        active_instance_id=selected_id,
    )

    return CommandPreviewResult(
        command,
        warnings=adapter_result.warnings,
        export_dir=target_dir,
        run_configuration=run_config,
        instance_count=len(adapter_result.execution_requests),
        execution_requests=adapter_result.execution_requests,
        adapter_result=adapter_result,
    )


def prepare_command_preview_legacy(ctx: ExecutionContext) -> CommandPreviewResult:
    """Fallback command preview from YAML stack paths when manifests are unavailable."""
    command = build_orchestrator_command(ctx)
    if not command.strip():
        return CommandPreviewResult("", ["No orchestrator command could be generated from the current paths."])
    return CommandPreviewResult(command)

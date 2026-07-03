"""Orchestrator adapter: load exported manifests and build execution requests (no execution)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from manifest_export import (
    MANIFEST_INDEX_FILENAME,
    MANIFEST_VERSION,
    load_instance_manifest,
    load_manifest_index,
)

SUPPORTED_MANIFEST_VERSIONS: frozenset[int] = frozenset({MANIFEST_VERSION})

REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "manifest_version",
    "instance_id",
    "topology",
    "assignments",
    "definitions",
    "network",
    "metadata",
)

REQUIRED_INDEX_FIELDS: tuple[str, ...] = (
    "manifest_version",
    "total_instances",
    "instance_files",
)


@dataclass
class ExecutionRequest:
    """One orchestrator-ready execution unit derived from an exported manifest."""

    instance_id: int
    manifest_path: Path
    manifest_version: int
    topology: dict[str, Any]
    assignments: dict[str, Any]
    definitions: dict[str, Any]
    network: dict[str, Any]
    metadata: dict[str, Any]
    combination: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    paths: dict[str, str] = field(default_factory=dict)
    resolved_paths: dict[str, Path] = field(default_factory=dict)
    experiment_state: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "manifest_path": str(self.manifest_path),
            "manifest_version": self.manifest_version,
            "topology": copy.deepcopy(self.topology),
            "assignments": copy.deepcopy(self.assignments),
            "definitions": copy.deepcopy(self.definitions),
            "network": copy.deepcopy(self.network),
            "metadata": copy.deepcopy(self.metadata),
            "combination": copy.deepcopy(self.combination),
            "labels": copy.deepcopy(self.labels),
            "paths": copy.deepcopy(self.paths),
            "resolved_paths": {k: str(v) for k, v in self.resolved_paths.items()},
            "experiment_state": copy.deepcopy(self.experiment_state),
        }


@dataclass
class OrchestratorAdapterResult:
    """Outcome of loading and validating exported manifests."""

    export_dir: Path
    index: dict[str, Any] = field(default_factory=dict)
    manifests: list[dict[str, Any]] = field(default_factory=list)
    manifest_paths: list[Path] = field(default_factory=list)
    execution_requests: list[ExecutionRequest] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors and bool(self.execution_requests)

    @property
    def manifest_version(self) -> int | None:
        raw = self.index.get("manifest_version")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @property
    def instance_count(self) -> int:
        return len(self.execution_requests)


def resolve_path(
    path_str: str,
    *,
    export_dir: Path,
    driver_root: Path | None = None,
    must_exist: bool = False,
) -> Path:
    """
    Resolve a path relative to export directory, then driver root, then cwd.

    Absolute paths are returned as-is (resolved).
    """
    text = str(path_str or "").strip()
    if not text:
        raise ValueError("Path string is empty.")

    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path not found: {resolved}")
        return resolved

    bases: list[Path] = [export_dir.resolve()]
    if driver_root is not None:
        bases.append(driver_root.resolve())

    for base in bases:
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved

    fallback = (export_dir / candidate).resolve()
    if must_exist and not fallback.exists():
        raise FileNotFoundError(f"Path not found: {fallback}")
    return fallback


def _coerce_version(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def validate_manifest_version(
    version: Any,
    *,
    supported: frozenset[int] = SUPPORTED_MANIFEST_VERSIONS,
    context: str = "manifest",
) -> list[str]:
    errors: list[str] = []
    v = _coerce_version(version)
    if v is None:
        errors.append(f"{context}: manifest_version is missing or invalid.")
        return errors
    if v not in supported:
        supported_list = ", ".join(str(x) for x in sorted(supported))
        errors.append(
            f"{context}: manifest_version {v} is not supported (supported: {supported_list})."
        )
    return errors


def validate_instance_manifest_document(
    manifest: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    supported: frozenset[int] = SUPPORTED_MANIFEST_VERSIONS,
) -> list[str]:
    label = manifest_path.name if manifest_path else "instance manifest"
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return [f"{label}: manifest must be a mapping."]

    errors.extend(
        validate_manifest_version(manifest.get("manifest_version"), supported=supported, context=label)
    )

    for key in REQUIRED_MANIFEST_FIELDS:
        if key not in manifest:
            errors.append(f"{label}: required field {key!r} is missing.")

    instance_id = manifest.get("instance_id")
    try:
        if instance_id is None or int(instance_id) < 1:
            errors.append(f"{label}: instance_id must be a positive integer.")
    except (TypeError, ValueError):
        errors.append(f"{label}: instance_id must be a positive integer.")

    for section in ("topology", "assignments", "definitions", "network", "metadata"):
        if section in manifest and not isinstance(manifest.get(section), dict):
            errors.append(f"{label}: {section!r} must be a mapping.")

    return errors


def validate_manifest_index_document(
    index: dict[str, Any],
    *,
    supported: frozenset[int] = SUPPORTED_MANIFEST_VERSIONS,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(index, dict):
        return [f"{MANIFEST_INDEX_FILENAME}: index must be a mapping."]

    errors.extend(
        validate_manifest_version(index.get("manifest_version"), supported=supported, context=MANIFEST_INDEX_FILENAME)
    )

    for key in REQUIRED_INDEX_FIELDS:
        if key not in index:
            errors.append(f"{MANIFEST_INDEX_FILENAME}: required field {key!r} is missing.")

    files = index.get("instance_files")
    if files is not None and not isinstance(files, list):
        errors.append(f"{MANIFEST_INDEX_FILENAME}: instance_files must be a list.")

    total = index.get("total_instances")
    try:
        total_n = int(total)
    except (TypeError, ValueError):
        total_n = -1
        errors.append(f"{MANIFEST_INDEX_FILENAME}: total_instances must be an integer.")

    if isinstance(files, list) and total_n >= 0 and len(files) != total_n:
        errors.append(
            f"{MANIFEST_INDEX_FILENAME}: total_instances ({total_n}) "
            f"does not match instance_files count ({len(files)})."
        )

    return errors


def _resolve_manifest_paths(
    paths: dict[str, Any],
    *,
    export_dir: Path,
    driver_root: Path | None,
) -> tuple[dict[str, Path], list[str]]:
    resolved: dict[str, Path] = {}
    warnings: list[str] = []
    if not isinstance(paths, dict):
        return resolved, warnings

    for key, raw in paths.items():
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            resolved[str(key)] = resolve_path(text, export_dir=export_dir, driver_root=driver_root, must_exist=True)
        except (ValueError, FileNotFoundError) as e:
            warnings.append(f"Path {key!r} ({text}): {e}")
    return resolved, warnings


def build_execution_request(
    manifest: dict[str, Any],
    manifest_path: Path,
    *,
    export_dir: Path,
    driver_root: Path | None = None,
) -> ExecutionRequest:
    """Construct an ExecutionRequest from a loaded manifest document."""
    paths_raw = manifest.get("paths") if isinstance(manifest.get("paths"), dict) else {}
    resolved_paths, _warnings = _resolve_manifest_paths(
        paths_raw, export_dir=export_dir, driver_root=driver_root
    )

    combination = manifest.get("combination") if isinstance(manifest.get("combination"), dict) else {}
    labels = manifest.get("labels") if isinstance(manifest.get("labels"), dict) else {}
    metadata = copy.deepcopy(manifest.get("metadata") or {})
    metadata.setdefault("manifest_path", str(manifest_path.resolve()))

    return ExecutionRequest(
        instance_id=int(manifest.get("instance_id", 0)),
        manifest_path=manifest_path.resolve(),
        manifest_version=int(manifest.get("manifest_version", MANIFEST_VERSION)),
        topology=copy.deepcopy(manifest.get("topology") or {}),
        assignments=copy.deepcopy(manifest.get("assignments") or {}),
        definitions=copy.deepcopy(manifest.get("definitions") or {}),
        network=copy.deepcopy(manifest.get("network") or {}),
        metadata=metadata,
        combination={str(k): str(v) for k, v in combination.items()},
        labels={str(k): str(v) for k, v in labels.items()},
        paths={str(k): str(v) for k, v in paths_raw.items()},
        resolved_paths=resolved_paths,
        experiment_state=copy.deepcopy(manifest.get("experiment_state") or {}),
    )


class OrchestratorAdapter:
    """
    Load exported manifest_index.yaml and instance manifests; build execution requests.

    Does not invoke Dylan's orchestrator or launch subprocesses.
    """

    def __init__(
        self,
        export_dir: Path | str,
        *,
        driver_root: Path | str | None = None,
        supported_versions: frozenset[int] = SUPPORTED_MANIFEST_VERSIONS,
    ) -> None:
        self.export_dir = Path(export_dir).expanduser().resolve()
        self.driver_root = Path(driver_root).expanduser().resolve() if driver_root else None
        self.supported_versions = supported_versions
        self._index: dict[str, Any] = {}
        self._manifests: list[dict[str, Any]] = []
        self._manifest_paths: list[Path] = []
        self._execution_requests: list[ExecutionRequest] = []
        self._errors: list[str] = []
        self._warnings: list[str] = []

    @property
    def index(self) -> dict[str, Any]:
        return copy.deepcopy(self._index)

    @property
    def execution_requests(self) -> list[ExecutionRequest]:
        return list(self._execution_requests)

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def load(self) -> OrchestratorAdapterResult:
        """Load manifest index and all instance manifests from export_dir."""
        self._index = {}
        self._manifests = []
        self._manifest_paths = []
        self._execution_requests = []
        self._errors = []
        self._warnings = []

        index_path = self.export_dir / MANIFEST_INDEX_FILENAME
        if not index_path.is_file():
            self._errors.append(f"Manifest index not found: {index_path}")
            return self._result()

        try:
            self._index = load_manifest_index(self.export_dir)
        except (ValueError, OSError) as e:
            self._errors.append(f"Could not read {MANIFEST_INDEX_FILENAME}: {e}")
            return self._result()

        self._errors.extend(
            validate_manifest_index_document(self._index, supported=self.supported_versions)
        )

        filenames = self._index.get("instance_files")
        if not isinstance(filenames, list) or not filenames:
            if not self._errors:
                self._errors.append(f"{MANIFEST_INDEX_FILENAME}: instance_files is empty.")
            return self._result()

        for filename in filenames:
            name = str(filename).strip()
            if not name:
                self._errors.append(f"{MANIFEST_INDEX_FILENAME}: instance filename cannot be empty.")
                continue
            manifest_path = self.export_dir / name
            if not manifest_path.is_file():
                self._errors.append(f"Instance manifest not found: {manifest_path}")
                continue
            try:
                manifest = load_instance_manifest(manifest_path)
            except (ValueError, OSError) as e:
                self._errors.append(f"Could not read {name}: {e}")
                continue

            doc_errors = validate_instance_manifest_document(
                manifest, manifest_path=manifest_path, supported=self.supported_versions
            )
            if doc_errors:
                self._errors.extend(doc_errors)
                continue

            self._manifests.append(manifest)
            self._manifest_paths.append(manifest_path.resolve())

        if self._errors:
            return self._result()

        expected = int(self._index.get("total_instances", len(self._manifest_paths)))
        if len(self._manifest_paths) != expected:
            self._errors.append(
                f"Expected {expected} instance manifest(s) but loaded {len(self._manifest_paths)}."
            )
            return self._result()

        return self.build_execution_requests()

    def build_execution_requests(self) -> OrchestratorAdapterResult:
        """Build execution requests from already-loaded manifests."""
        if not self._manifest_paths or not self._manifests:
            if not self._errors:
                self._errors.append("No instance manifests loaded.")
            return self._result()

        requests: list[ExecutionRequest] = []
        for manifest_path, manifest in zip(self._manifest_paths, self._manifests, strict=True):
            req = build_execution_request(
                manifest,
                manifest_path,
                export_dir=self.export_dir,
                driver_root=self.driver_root,
            )
            _, path_warnings = _resolve_manifest_paths(
                req.paths, export_dir=self.export_dir, driver_root=self.driver_root
            )
            self._warnings.extend(path_warnings)
            requests.append(req)

        self._execution_requests = requests
        return self._result()

    def _result(self) -> OrchestratorAdapterResult:
        return OrchestratorAdapterResult(
            export_dir=self.export_dir,
            index=copy.deepcopy(self._index),
            manifests=copy.deepcopy(self._manifests),
            manifest_paths=list(self._manifest_paths),
            execution_requests=list(self._execution_requests),
            errors=list(self._errors),
            warnings=list(self._warnings),
        )


def format_execution_preview(result: OrchestratorAdapterResult) -> str:
    """Multi-line summary for the Execution Preview panel."""
    lines = ["Execution Preview", ""]

    if not result.export_dir.exists():
        lines.append("Export directory: (not set)")
        lines.append("")
        lines.append("Validation status: No manifests loaded.")
        lines.append("")
        lines.append("Load an export directory containing manifest_index.yaml.")
        return "\n".join(lines).strip()

    lines.append(f"Export directory: {result.export_dir}")
    lines.append("")

    version = result.manifest_version
    lines.append(f"Manifest version: {version if version is not None else '(unknown)'}")
    lines.append(f"Total manifests: {len(result.manifest_paths)}")
    lines.append(f"Instance count: {result.instance_count}")
    lines.append("")

    if result.errors:
        lines.append("Validation status: FAILED")
        lines.append("")
        for err in result.errors[:10]:
            lines.append(f"• {err}")
        if len(result.errors) > 10:
            lines.append(f"• … and {len(result.errors) - 10} more.")
    elif result.execution_requests:
        lines.append("Validation status: OK")
        lines.append("")
        lines.append("Execution requests ready (not submitted).")
        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warn in result.warnings[:6]:
                lines.append(f"• {warn}")
            if len(result.warnings) > 6:
                lines.append(f"• … and {len(result.warnings) - 6} more.")
    else:
        lines.append("Validation status: No execution requests built.")

    return "\n".join(lines).strip()

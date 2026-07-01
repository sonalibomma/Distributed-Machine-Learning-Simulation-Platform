"""Shared resolution for YAML stack files referenced by driver.yaml.

Driver files authored on a cluster often store absolute paths
(e.g. ``/homes/user/project/configs/master/permutations.yaml``) that do not
exist on the machine running the GUI. To make a single driver.yaml upload
populate every tab, resolution tries, in order:

1. The stored path as-is (absolute, or relative to the current directory).
2. The stored path relative to the driver.yaml directory.
3. Progressively shorter *tails* of the stored path joined to the driver
   directory (handles a preserved sub-tree like ``configs/master/<file>``).
4. The bare filename beside driver.yaml.
5. The bare filename found anywhere beneath the driver directory.
6. A default filename beside driver.yaml (and beneath it).
"""

from __future__ import annotations

import re
from pathlib import Path


def _first_file_under(root: Path, filename: str) -> Path | None:
    try:
        matches = sorted(p for p in root.rglob(filename) if p.is_file())
    except OSError:
        return None
    return matches[0].resolve() if matches else None


def _find_by_stem(root: Path, filename: str) -> Path | None:
    """Find a file beneath ``root`` whose stem matches ``filename``'s stem,
    ignoring case and accepting either a .yaml or .yml extension.

    Handles driver.yaml references like ``permutations.yml`` or ``Permutations.yaml``
    that differ from the canonical name only by case or extension.
    """
    target_stem = Path(filename).stem.casefold()
    if not target_stem:
        return None
    try:
        candidates = [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.casefold() in (".yaml", ".yml")
            and p.stem.casefold() == target_stem
        ]
    except OSError:
        return None
    return sorted(candidates)[0].resolve() if candidates else None


def _find_duplicate(root: Path, filename: str) -> Path | None:
    """Find a duplicate-named copy beneath ``root`` (.yaml/.yml).

    Cloud sync and Finder rename copies as ``permutations 1.yaml``,
    ``permutations(1).yaml`` or ``permutations copy.yaml``. When a driver.yaml
    references ``permutations.yaml`` but only such a copy exists locally, match
    it so a single driver upload still populates the tab.
    """
    target_stem = Path(filename).stem.casefold()
    if not target_stem:
        return None
    # target stem followed by " 1" / "(1)" / " copy" / " copy 2", etc.
    pattern = re.compile(
        re.escape(target_stem) + r"(?:\s*\(\d+\)|\s+\d+|\s+copy(?:\s+\d+)?)"
    )
    try:
        candidates = [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.casefold() in (".yaml", ".yml")
            and pattern.fullmatch(p.stem.casefold())
        ]
    except OSError:
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda p: (len(p.stem), str(p)))
    return candidates[0].resolve()


def resolve_stack_path(
    path_str: str,
    default_filename: str = "",
    *,
    driver_file: Path | str | None = None,
) -> Path | None:
    """Resolve a YAML stack file path with driver-relative fallbacks."""
    resolved, _ = resolve_stack_path_verbose(
        path_str, default_filename, driver_file=driver_file
    )
    return resolved


def resolve_stack_path_verbose(
    path_str: str,
    default_filename: str = "",
    *,
    driver_file: Path | str | None = None,
) -> tuple[Path | None, list[str]]:
    """Like :func:`resolve_stack_path` but also return human-readable attempts.

    The attempts list records each location that was checked and whether it
    matched, which is invaluable when a driver.yaml from another machine points
    at paths that do not exist locally.
    """
    raw = str(path_str or "").strip()
    driver_dir = Path(driver_file).resolve().parent if driver_file else None
    attempts: list[str] = []

    def _check(label: str, candidate: Path) -> Path | None:
        try:
            ok = candidate.is_file()
        except OSError:
            ok = False
        attempts.append(f"{'FOUND' if ok else 'miss '} [{label}] {candidate}")
        return candidate.resolve() if ok else None

    if raw:
        candidate = Path(raw)

        # 1. As-is (absolute, or relative to the current working directory).
        hit = _check("as-is", candidate)
        if hit is not None:
            return hit, attempts

        if driver_dir is not None:
            # 2. Relative to the driver directory.
            if not candidate.is_absolute():
                hit = _check("driver-relative", driver_dir / candidate)
                if hit is not None:
                    return hit, attempts

            # 3. Progressively shorter path tails joined to the driver dir.
            parts = candidate.parts
            if candidate.is_absolute() and parts:
                parts = parts[1:]
            for start in range(len(parts)):
                tail = Path(*parts[start:])
                hit = _check("path-tail", driver_dir / tail)
                if hit is not None:
                    return hit, attempts

            # 4. The bare filename beside driver.yaml.
            hit = _check("beside-driver", driver_dir / candidate.name)
            if hit is not None:
                return hit, attempts

            # 5. The bare filename anywhere beneath the driver directory.
            found = _first_file_under(driver_dir, candidate.name)
            attempts.append(
                f"{'FOUND' if found else 'miss '} [under-driver] "
                f"{driver_dir}/**/{candidate.name}"
            )
            if found is not None:
                return found, attempts

            # 5b. Same stem with .yaml/.yml and any casing, beneath the driver.
            found = _find_by_stem(driver_dir, candidate.name)
            attempts.append(
                f"{'FOUND' if found else 'miss '} [stem/ext-insensitive] "
                f"{driver_dir}/**/{Path(candidate.name).stem}.(yaml|yml)"
            )
            if found is not None:
                return found, attempts

            # 5c. A duplicate-named copy (e.g. "permutations 1.yaml").
            found = _find_duplicate(driver_dir, candidate.name)
            attempts.append(
                f"{'FOUND' if found else 'miss '} [duplicate-copy] "
                f"{driver_dir}/**/{Path(candidate.name).stem} (1|copy).(yaml|yml)"
            )
            if found is not None:
                return found, attempts
        else:
            attempts.append("miss  [driver-relative] driver.yaml location unknown")

    if driver_dir is not None and default_filename:
        # 6. The default filename beside driver.yaml, then beneath it.
        hit = _check("default-beside-driver", driver_dir / default_filename)
        if hit is not None:
            return hit, attempts
        found = _first_file_under(driver_dir, default_filename)
        attempts.append(
            f"{'FOUND' if found else 'miss '} [default-under-driver] "
            f"{driver_dir}/**/{default_filename}"
        )
        if found is not None:
            return found, attempts

        found = _find_by_stem(driver_dir, default_filename)
        attempts.append(
            f"{'FOUND' if found else 'miss '} [default-stem/ext-insensitive] "
            f"{driver_dir}/**/{Path(default_filename).stem}.(yaml|yml)"
        )
        if found is not None:
            return found, attempts

        found = _find_duplicate(driver_dir, default_filename)
        attempts.append(
            f"{'FOUND' if found else 'miss '} [default-duplicate-copy] "
            f"{driver_dir}/**/{Path(default_filename).stem} (1|copy).(yaml|yml)"
        )
        if found is not None:
            return found, attempts

    return None, attempts

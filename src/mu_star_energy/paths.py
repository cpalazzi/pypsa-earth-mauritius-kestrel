"""Project data path conventions aligned with mu-star."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root, allowing an explicit environment override."""
    override = os.environ.get("MU_STAR_ENERGY_REPO")
    if override:
        return Path(override).expanduser().resolve()

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "pypsa-earth").exists():
            return candidate
    raise RuntimeError("Could not locate the mu-star energy repository root")


def data_root() -> Path:
    """Return the shared data root, allowing OneDrive or another external location."""
    override = os.environ.get("MU_STAR_DATA_ROOT")
    return Path(override).expanduser().resolve() if override else repo_root() / "data"


def incoming_energy_dir() -> Path:
    return data_root() / "incoming" / "energy"


def processed_energy_dir() -> Path:
    return data_root() / "processed" / "energy"


def output_energy_dir() -> Path:
    return data_root() / "out" / "energy"


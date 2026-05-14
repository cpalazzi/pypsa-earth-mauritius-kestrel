# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Project-level runtime patches.

This module is imported automatically by Python (if present on ``sys.path``)
right after the standard ``site`` initialization.  We use it to apply small
compatibility fixes without waiting for upstream releases.

Currently we patch :mod:`earth_osm.gfk_download` so checksum verification works
with Geofabrik ``.osm.pbf.md5`` files that are served gzip-compressed.
"""

from __future__ import annotations

import gzip
from typing import Optional, Tuple

from earth_osm import gfk_download

try:
    import pulp
except Exception:  # pragma: no cover - optional dependency
    pulp = None


def _parse_md5_file(md5_path: str) -> Tuple[str, Optional[str]]:
    """Read an MD5 checksum file, handling optional gzip compression."""
    with open(md5_path, "rb") as f:
        payload = f.read()

    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)

    text = payload.decode("ascii").strip()
    if not text:
        raise ValueError(f"MD5 file {md5_path} is empty")

    parts = text.split()
    checksum = parts[0].lower()
    remote_name: Optional[str] = None

    for candidate in parts[1:]:
        cleaned = candidate.lstrip("*")
        if cleaned.endswith(".osm.pbf"):
            remote_name = cleaned
            break

    return checksum, remote_name


def _verify_pbf(pbf_inputfile: str, pbf_md5file: str) -> bool:
    """Verify a downloaded PBF file against its (possibly gzipped) MD5."""
    local_md5 = gfk_download.calculate_md5(pbf_inputfile)
    remote_md5, _ = _parse_md5_file(pbf_md5file)
    return local_md5 == remote_md5


# Apply monkey patches so downstream code transparently benefits from gzip
# support until the upstream package includes this behaviour.
gfk_download._parse_md5_file = _parse_md5_file

# Keep the public name used elsewhere in the codebase.
gfk_download.verify_pbf = _verify_pbf

# Compat shim: some dependencies expect pulp.list_solvers (snake case).
if pulp is not None and not hasattr(pulp, "list_solvers") and hasattr(pulp, "listSolvers"):
    pulp.list_solvers = pulp.listSolvers

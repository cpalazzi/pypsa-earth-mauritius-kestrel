# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import gzip
from pathlib import Path

import earth_osm.gfk_download as gfk_download


def test_verify_pbf_supports_gzipped_md5(tmp_path: Path):
    # Create a dummy PBF file
    pbf_file = tmp_path / "example.osm.pbf"
    pbf_file.write_bytes(b"example data")

    # Build a gzip-compressed MD5 file matching the dummy PBF
    checksum = gfk_download.calculate_md5(pbf_file)
    md5_payload = f"{checksum} {pbf_file.name}\n".encode("ascii")
    md5_file = tmp_path / "example.osm.pbf.md5"
    md5_file.write_bytes(gzip.compress(md5_payload))

    assert gfk_download.verify_pbf(str(pbf_file), str(md5_file))

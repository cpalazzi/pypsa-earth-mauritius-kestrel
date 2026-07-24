import pytest

from mu_star_energy.cli import build_parser


def test_run_interruptions_network_selector_is_unambiguous():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run-interruptions",
                "--network",
                "data/1-processed/energy/networks/base/base.nc",
                "--network-source",
                "base",
            ]
        )

    with pytest.raises(SystemExit):
        parser.parse_args(["run-interruptions"])


def test_build_network_accepts_inferred_region_selector():
    parser = build_parser()

    args = parser.parse_args(["build-network", "inferred", "--region", "rodrigues"])

    assert args.source == "inferred"
    assert args.region == "rodrigues"
    assert args.network_type == "all"
    assert args.max_anchor_distance_m == 1000.0
    assert args.nightlight_aoi is None
    assert args.nightlights is None
    assert args.nightlight_threshold == 0.1
    assert args.nightlight_support_distance_m == 1000.0
    assert args.inferred_reference_line_length_km == 10_492.2


def test_build_network_accepts_reviewed_data_inferred_source():
    parser = build_parser()

    args = parser.parse_args(
        ["build-network", "inferred-data", "--region", "mauritius-rodrigues"]
    )

    assert args.source == "inferred-data"
    assert args.region == "mauritius-rodrigues"


def test_build_network_region_is_open_ended():
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-network",
            "inferred",
            "--region",
            "Rodrigues, Mauritius",
            "--allow-download",
        ]
    )

    assert args.region == "Rodrigues, Mauritius"
    assert args.allow_download is True

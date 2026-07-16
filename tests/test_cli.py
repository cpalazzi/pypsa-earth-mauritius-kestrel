import pytest

from mu_star_energy.cli import build_parser


def test_run_interruptions_network_selector_is_unambiguous():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run-interruptions",
                "--network",
                "data/1-processed/energy/networks/base.nc",
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

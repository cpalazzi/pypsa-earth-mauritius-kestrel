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

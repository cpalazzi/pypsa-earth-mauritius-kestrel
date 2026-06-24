"""Command-line entry points for the preprocessing workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mu_star_energy.intake import prepare_collaborator_data
from mu_star_energy.paths import incoming_energy_dir, processed_energy_dir


def _prepare_assets(args: argparse.Namespace) -> None:
    outputs = prepare_collaborator_data(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mu-star-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-assets")
    prepare.add_argument(
        "--input-dir", type=Path, default=incoming_energy_dir() / "collaborator"
    )
    prepare.add_argument(
        "--output-dir", type=Path, default=processed_energy_dir() / "collaborator"
    )
    prepare.set_defaults(func=_prepare_assets)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

"""Command-line entry points for the preprocessing workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from mu_star_energy.intake import prepare_collaborator_data
from mu_star_energy.topology import build_substation_topology


def _prepare_assets(args: argparse.Namespace) -> None:
    outputs = prepare_collaborator_data(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, indent=2))


def _build_topology(args: argparse.Namespace) -> None:
    processed = Path(args.processed_dir)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    substations = gpd.read_parquet(processed / "substations.parquet")
    routes = gpd.read_parquet(processed / "transmission_routes.parquet")
    result = build_substation_topology(
        substations,
        routes,
        snap_tolerance_m=args.snap_tolerance_m,
        default_voltage_kv=args.default_voltage_kv,
    )
    result.buses.to_parquet(output / "buses.parquet")
    result.lines.to_parquet(output / "lines.parquet")
    report = {
        "buses": len(result.buses),
        "lines": len(result.lines),
        "ignored_route_parts": result.ignored_route_parts,
        "ratings_complete": bool(
            not result.lines.empty and result.lines["s_nom_mva"].notna().all()
        ),
    }
    (output / "topology_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mu-star-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-assets")
    prepare.add_argument("--input-dir", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(func=_prepare_assets)

    topology = subparsers.add_parser("build-topology")
    topology.add_argument("--processed-dir", required=True)
    topology.add_argument("--output-dir", required=True)
    topology.add_argument("--snap-tolerance-m", type=float, default=2500)
    topology.add_argument("--default-voltage-kv", type=float, default=66)
    topology.set_defaults(func=_build_topology)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


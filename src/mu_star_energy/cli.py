"""Command-line entry points for asset preparation, interruption runs and the
synthetic distribution experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from mu_star_energy.distribution_network import (
    build_synthetic_distribution_graph,
    write_synthetic_distribution_tables,
)
from mu_star_energy.intake import prepare_collaborator_data
from mu_star_energy.paths import incoming_energy_dir, output_energy_dir, processed_energy_dir
from mu_star_energy.runner import run_interruption_analysis


def _prepare_assets(args: argparse.Namespace) -> None:
    outputs = prepare_collaborator_data(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, indent=2))


def _run_interruptions(args: argparse.Namespace) -> None:
    outputs = run_interruption_analysis(
        Path(args.input_dir),
        Path(args.output_dir),
        solver_name=args.solver,
        value_of_lost_load=args.value_of_lost_load,
        disruptions_path=args.disruptions,
        generator_availability_path=args.generator_availability,
        require_no_baseline_shedding=args.require_no_baseline_shedding,
        export_networks=not args.skip_network_export,
    )
    print(
        json.dumps(
            {
                key: str(value) if value is not None else None
                for key, value in outputs.__dict__.items()
            },
            indent=2,
        )
    )


def _read_optional_vector(path: Path | None):
    if path is None or not path.exists():
        return None
    if path.suffix.lower() == ".parquet":
        return gpd.read_parquet(path)
    return gpd.read_file(path)


def _prepare_synthetic_distribution(args: argparse.Namespace) -> None:
    if not args.enable_synthetic_distribution:
        raise SystemExit(
            "Pass --enable-synthetic-distribution to build the labelled synthetic layer."
        )
    substations = gpd.read_parquet(args.substations)
    gridfinder_lines = _read_optional_vector(args.gridfinder_lines)
    osm_distribution_lines = _read_optional_vector(args.osm_distribution_lines)
    if gridfinder_lines is None and osm_distribution_lines is None:
        raise FileNotFoundError(
            "No GridFinder or OSM distribution line file was found for the synthetic layer"
        )
    graph = build_synthetic_distribution_graph(
        substations,
        gridfinder_lines=gridfinder_lines,
        osm_distribution_lines=osm_distribution_lines,
        max_anchor_distance_m=args.max_anchor_distance_m,
    )
    outputs = write_synthetic_distribution_tables(graph, args.output_dir)
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

    run = subparsers.add_parser("run-interruptions")
    run.add_argument(
        "--input-dir",
        type=Path,
        default=processed_energy_dir() / "collaborator",
        help="Folder containing reviewed buses, lines, generators, demand and service weights.",
    )
    run.add_argument(
        "--output-dir",
        type=Path,
        default=output_energy_dir(),
        help="Folder where metrics, unmet-demand tables and networks are written.",
    )
    run.add_argument(
        "--disruptions",
        type=Path,
        default=None,
        help=(
            "Optional CSV with component, asset_id and available_fraction; "
            "damage_fraction or fraction are also accepted as damage fractions."
        ),
    )
    run.add_argument(
        "--generator-availability",
        type=Path,
        default=None,
        help=(
            "Optional timestamped CSV with one availability-fraction column per generator_id."
        ),
    )
    run.add_argument("--solver", default="highs")
    run.add_argument("--value-of-lost-load", type=float, default=10_000)
    run.add_argument("--require-no-baseline-shedding", action="store_true")
    run.add_argument("--skip-network-export", action="store_true")
    run.set_defaults(func=_run_interruptions)

    synthetic = subparsers.add_parser("prepare-synthetic-distribution")
    synthetic.add_argument(
        "--enable-synthetic-distribution",
        action="store_true",
        help="Required safety flag; keeps GridFinder/OSM feeders outside the baseline.",
    )
    synthetic.add_argument(
        "--substations",
        type=Path,
        default=processed_energy_dir() / "collaborator" / "snapped_substations.parquet",
    )
    synthetic.add_argument(
        "--gridfinder-lines",
        type=Path,
        default=incoming_energy_dir() / "gridfinder" / "grid.gpkg",
    )
    synthetic.add_argument(
        "--osm-distribution-lines",
        type=Path,
        default=incoming_energy_dir() / "osm" / "distribution_lines.parquet",
    )
    synthetic.add_argument(
        "--output-dir",
        type=Path,
        default=processed_energy_dir() / "synthetic_distribution",
    )
    synthetic.add_argument("--max-anchor-distance-m", type=float, default=500)
    synthetic.set_defaults(func=_prepare_synthetic_distribution)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

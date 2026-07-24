"""Command-line entry points for asset preparation, interruption runs and the
inferred distribution experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from mu_star_energy.distribution_network import (
    DEFAULT_MAX_ANCHOR_DISTANCE_M,
    build_inferred_distribution_graph,
    write_inferred_distribution_tables,
)
from mu_star_energy.intake import prepare_provided_data
from mu_star_energy.network_source import build_network
from mu_star_energy.osm import REGIONS, REGION_GROUPS
from mu_star_energy.paths import (
    incoming_energy_dir,
    network_output_dir,
    output_energy_dir,
    processed_energy_dir,
)
from mu_star_energy.runner import run_interruption_analysis


def _prepare_assets(args: argparse.Namespace) -> None:
    outputs = prepare_provided_data(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, indent=2))


def _run_interruptions(args: argparse.Namespace) -> None:
    network_path = args.network
    if args.network_source is not None:
        network_path = (
            network_output_dir()
            / args.network_source
            / f"{args.network_source}.nc"
        )
    outputs = run_interruption_analysis(
        Path(args.input_dir),
        Path(args.output_dir),
        network_path=network_path,
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


def _build_network(args: argparse.Namespace) -> None:
    outputs = build_network(
        args.source,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        region=args.region,
        output_name=args.output_name,
        overwrite=args.overwrite,
        allow_download=args.allow_download,
        network_type=args.network_type,
        nightlight_aoi_path=args.nightlight_aoi,
        nightlights_path=args.nightlights,
        nightlight_threshold=args.nightlight_threshold,
        nightlight_support_distance_m=args.nightlight_support_distance_m,
        max_anchor_distance_m=args.max_anchor_distance_m,
        inferred_voltage_kv=args.inferred_voltage_kv,
        inferred_capacity_mva=args.inferred_capacity_mva,
        export_root=args.export_root,
        reference_line_length_km=args.reference_line_length_km,
        inferred_reference_line_length_km=args.inferred_reference_line_length_km,
        line_length_tolerance_fraction=args.line_length_tolerance_fraction,
        reference_generation_capacity_mw=args.reference_generation_capacity_mw,
        generation_capacity_tolerance_fraction=(args.generation_capacity_tolerance_fraction),
        base_route_gap_tolerance_m=args.base_route_gap_tolerance_m,
        base_default_voltage_kv=args.base_default_voltage_kv,
        base_topology_capacity_mva=args.base_topology_capacity_mva,
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


def _prepare_inferred_distribution(args: argparse.Namespace) -> None:
    if not args.enable_inferred_distribution:
        raise SystemExit(
            "Pass --enable-inferred-distribution to build the labelled inferred layer."
        )
    substations = gpd.read_parquet(args.substations)
    precomputed_lines = _read_optional_vector(args.precomputed_lines)
    osm_distribution_lines = _read_optional_vector(args.osm_distribution_lines)
    if precomputed_lines is None and osm_distribution_lines is None:
        raise FileNotFoundError(
            "No precomputed or OSM distribution line file was found for the inferred layer"
        )
    graph = build_inferred_distribution_graph(
        substations,
        precomputed_lines=precomputed_lines,
        osm_distribution_lines=osm_distribution_lines,
        max_anchor_distance_m=args.max_anchor_distance_m,
    )
    outputs = write_inferred_distribution_tables(graph, args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.__dict__.items()}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mu-star-energy")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-assets")
    prepare.add_argument("--input-dir", type=Path, default=incoming_energy_dir() / "provided")
    prepare.add_argument("--output-dir", type=Path, default=processed_energy_dir() / "provided")
    prepare.set_defaults(func=_prepare_assets)

    build = subparsers.add_parser("build-network")
    build.add_argument(
        "source",
        choices=["base", "inferred", "inferred-osm", "inferred-data"],
    )
    build.add_argument(
        "--region",
        default=None,
        help=(
            "Required for inferred sources: any OSM/Nominatim query (e.g. "
            "'Rodrigues, Mauritius'). Shortcuts: "
            + ", ".join(sorted({*REGIONS, *REGION_GROUPS}))
            + "."
        ),
    )
    build.add_argument(
        "--input-dir",
        type=Path,
        default=processed_energy_dir() / "provided",
        help=(
            "Folder containing reviewed/intermediate inputs "
            "(used by base and inferred-data)."
        ),
    )
    build.add_argument(
        "--output-dir",
        type=Path,
        default=network_output_dir(),
        help="Root folder where one subdirectory per named network result is written.",
    )
    build.add_argument(
        "--export-root",
        type=Path,
        default=network_output_dir(),
        help=(
            "Root for source-specific human CSVs and validation reports "
            "(default: data/2-out/energy/networks, alongside the .nc)."
        ),
    )
    build.add_argument(
        "--output-name",
        default=None,
        help=(
            "Result-directory and file stem "
            "(default: 'base', 'inferred-osm-<region>', or "
            "'inferred-data-<region>')."
        ),
    )
    build.add_argument(
        "--overwrite",
        action="store_true",
        help="Rebuild and overwrite an existing network file.",
    )
    build.add_argument(
        "--allow-download",
        action="store_true",
        help="Permit fetching the OSM road envelope and power features when uncached.",
    )
    build.add_argument(
        "--network-type",
        default="all",
        help=(
            "OSM detail retained around VIIRS nightlight targets. Use "
            "'all' (default)."
        ),
    )
    build.add_argument(
        "--nightlight-aoi",
        type=Path,
        default=None,
        help="Polygon GeoParquet defining the nightlight analysis area.",
    )
    build.add_argument(
        "--nightlights",
        type=Path,
        default=None,
        help="Reviewed single-band VIIRS raster used to identify connection targets.",
    )
    build.add_argument("--nightlight-threshold", type=float, default=0.1)
    build.add_argument(
        "--nightlight-support-distance-m",
        type=float,
        default=1000,
        help=(
            "Retain OSM roads within this distance of a VIIRS nightlight "
            "target (default: 1000 m)."
        ),
    )
    build.add_argument(
        "--max-anchor-distance-m",
        type=float,
        default=DEFAULT_MAX_ANCHOR_DISTANCE_M,
    )
    build.add_argument("--inferred-voltage-kv", type=float, default=11)
    build.add_argument("--inferred-capacity-mva", type=float, default=5)
    build.add_argument("--reference-line-length-km", type=float, default=478.9)
    build.add_argument(
        "--inferred-reference-line-length-km",
        type=float,
        default=10_492.2,
        help="Published CEB whole-network circuit length used to validate source=inferred.",
    )
    build.add_argument("--line-length-tolerance-fraction", type=float, default=0.35)
    build.add_argument(
        "--reference-generation-capacity-mw",
        type=float,
        default=881.56,
    )
    build.add_argument(
        "--generation-capacity-tolerance-fraction",
        type=float,
        default=0.10,
    )
    build.add_argument("--base-route-gap-tolerance-m", type=float, default=75)
    build.add_argument("--base-default-voltage-kv", type=float, default=66)
    build.add_argument("--base-topology-capacity-mva", type=float, default=10_000)
    build.set_defaults(func=_build_network)

    run = subparsers.add_parser("run-interruptions")
    run.add_argument(
        "--input-dir",
        type=Path,
        default=processed_energy_dir() / "provided",
        help="Folder containing demand, service weights and related run inputs.",
    )
    run.add_argument(
        "--output-dir",
        type=Path,
        default=output_energy_dir(),
        help="Folder where metrics, unmet-demand tables and networks are written.",
    )
    network_selector = run.add_mutually_exclusive_group(required=True)
    network_selector.add_argument(
        "--network",
        type=Path,
        default=None,
        help="Saved PyPSA .nc topology network to load.",
    )
    network_selector.add_argument(
        "--network-source",
        choices=["base", "inferred"],
        default=None,
        help="Load data/2-out/energy/networks/<source>.nc.",
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
        help=("Optional timestamped CSV with one availability-fraction column per generator_id."),
    )
    run.add_argument("--solver", default="highs")
    run.add_argument("--value-of-lost-load", type=float, default=10_000)
    run.add_argument("--require-no-baseline-shedding", action="store_true")
    run.add_argument("--skip-network-export", action="store_true")
    run.set_defaults(func=_run_interruptions)

    inferred = subparsers.add_parser("prepare-inferred-distribution")
    inferred.add_argument(
        "--enable-inferred-distribution",
        action="store_true",
        help="Required safety flag; keeps inferred/OSM feeders outside the baseline.",
    )
    inferred.add_argument(
        "--substations",
        type=Path,
        default=processed_energy_dir() / "provided" / "snapped_substations.parquet",
    )
    inferred.add_argument(
        "--precomputed-lines",
        type=Path,
        default=incoming_energy_dir() / "inferred" / "distribution_lines.gpkg",
    )
    inferred.add_argument(
        "--osm-distribution-lines",
        type=Path,
        default=incoming_energy_dir() / "osm" / "distribution_lines.parquet",
    )
    inferred.add_argument(
        "--output-dir",
        type=Path,
        default=processed_energy_dir() / "inferred_distribution",
    )
    inferred.add_argument(
        "--max-anchor-distance-m",
        type=float,
        default=DEFAULT_MAX_ANCHOR_DISTANCE_M,
    )
    inferred.set_defaults(func=_prepare_inferred_distribution)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

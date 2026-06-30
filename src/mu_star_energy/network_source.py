"""Build and save PyPSA networks from named input sources (base or inferred)."""

from __future__ import annotations

import json
from calendar import month_abbr
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
import pypsa
from shapely.geometry import Point

from mu_star_energy.distribution_network import (
    METRIC_CRS,
    build_inferred_distribution_graph,
    write_inferred_distribution_tables,
)
from mu_star_energy.network import assert_fixed_capacity, build_operational_network
from mu_star_energy.paths import incoming_energy_dir, processed_energy_dir
from mu_star_energy.runner import read_time_series_csv

BASE_REQUIRED_FILES = (
    "snapped_substations.parquet",
    "lines.csv",
    "generators.csv",
    "demand_profile.csv",
    "service_weights.csv",
)


@dataclass(frozen=True)
class NetworkBuildOutputs:
    network: Path
    metadata: Path
    inferred_nodes: Path | None = None
    inferred_edges: Path | None = None
    inferred_metadata: Path | None = None


def _read_optional_vector(path: Path | None) -> gpd.GeoDataFrame | None:
    if path is None or not path.exists():
        return None
    if path.suffix.lower() == ".parquet":
        return gpd.read_parquet(path)
    return gpd.read_file(path)


def _missing_files(input_dir: Path, names: tuple[str, ...]) -> list[Path]:
    return [input_dir / name for name in names if not (input_dir / name).exists()]


def _load_reviewed_inputs(input_dir: Path) -> tuple[
    gpd.GeoDataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    missing = _missing_files(input_dir, BASE_REQUIRED_FILES)
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Cannot build the reviewed base network until these files exist:\n"
            f"{formatted}"
        )

    buses = gpd.read_parquet(input_dir / "snapped_substations.parquet")
    lines = pd.read_csv(input_dir / "lines.csv")
    generators = pd.read_csv(input_dir / "generators.csv")
    demand = read_time_series_csv(input_dir / "demand_profile.csv", label="demand_profile")
    service_weights = pd.read_csv(input_dir / "service_weights.csv")
    return buses, lines, generators, demand, service_weights


def _write_network(path: Path, network: pypsa.Network) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_fixed_capacity(network)
    network.export_to_netcdf(path)
    return path


def _write_metadata(path: Path, metadata: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _build_base_network(
    *,
    input_dir: Path,
    network_path: Path,
    metadata_path: Path,
    generator_availability_path: Path | None,
    value_of_lost_load: float,
) -> NetworkBuildOutputs:
    buses, lines, generators, demand, service_weights = _load_reviewed_inputs(input_dir)
    generator_availability = (
        read_time_series_csv(generator_availability_path, label="generator_availability")
        if generator_availability_path
        else None
    )
    network = build_operational_network(
        buses,
        lines,
        generators,
        demand,
        service_weights,
        generator_availability=generator_availability,
        value_of_lost_load=value_of_lost_load,
    )
    _write_network(network_path, network)
    _write_metadata(
        metadata_path,
        {
            "source": "base",
            "input_dir": str(input_dir),
            "network": str(network_path),
            "snapshots": len(network.snapshots),
            "buses": len(network.buses),
            "lines": len(network.lines),
            "generators": int(
                network.generators.carrier.ne("load_shedding").sum()
            ),
            "loads": len(network.loads),
            "inferred": False,
        },
    )
    return NetworkBuildOutputs(network=network_path, metadata=metadata_path)


def _latest_peak_demand_profile(input_dir: Path) -> pd.DataFrame:
    path = input_dir / "monthly_peak_demand_mw.csv"
    if not path.exists():
        raise FileNotFoundError(
            "demand_profile.csv is missing. Pass --allow-provisional-demand to "
            "use monthly_peak_demand_mw.csv, or supply a reviewed demand profile."
        )
    peaks = pd.read_csv(path)
    value_columns = [column for column in peaks.columns if column != "year"]
    long = peaks.melt(
        id_vars="year",
        value_vars=value_columns,
        var_name="month",
        value_name="demand_mw",
    )
    long["demand_mw"] = pd.to_numeric(long["demand_mw"], errors="coerce")
    long = long.dropna(subset=["demand_mw"])
    if long.empty:
        raise ValueError(f"{path} does not contain a usable demand value")
    month_order = {name: index for index, name in enumerate(month_abbr) if name}
    long["month_number"] = long["month"].map(month_order)
    long = long.dropna(subset=["month_number"])
    if long.empty:
        raise ValueError(f"{path} month columns must use abbreviated month names")
    row = long.sort_values(["year", "month_number"]).iloc[-1]
    timestamp = pd.Timestamp(int(row["year"]), int(row["month_number"]), 1)
    return pd.DataFrame({"demand_mw": [float(row["demand_mw"])]}, index=[timestamp])


def _load_demand_profile(input_dir: Path, *, allow_provisional_demand: bool) -> pd.DataFrame:
    path = input_dir / "demand_profile.csv"
    if path.exists():
        return read_time_series_csv(path, label="demand_profile")
    if allow_provisional_demand:
        return _latest_peak_demand_profile(input_dir)
    raise FileNotFoundError(
        f"{path} is missing. Supply a reviewed demand profile, or pass "
        "--allow-provisional-demand for a one-snapshot network."
    )


def _empty_generators() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "generator_id",
            "bus_id",
            "carrier",
            "capacity_mw",
            "capacity_basis",
            "marginal_cost",
        ]
    )


def _load_generators(input_dir: Path, *, inferred_bus_ids: bool) -> pd.DataFrame:
    path = input_dir / "generators.csv"
    if not path.exists():
        return _empty_generators()
    generators = pd.read_csv(path)
    if inferred_bus_ids and not generators.empty:
        generators = generators.copy()
        generators["bus_id"] = "bus::" + generators["bus_id"].astype(str)
    return generators


def _node_bus_frame(graph: nx.Graph) -> gpd.GeoDataFrame:
    rows = [
        {
            "bus_id": node,
            "kind": attrs.get("kind"),
            "inferred": bool(attrs.get("inferred", False)),
            "source": attrs.get("source", "reviewed_substation"),
            "v_nom_kv": attrs.get("v_nom_kv"),
            "geometry": Point(float(attrs["x"]), float(attrs["y"])),
        }
        for node, attrs in graph.nodes(data=True)
        if "x" in attrs and "y" in attrs
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=METRIC_CRS).to_crs("EPSG:4326")


def _graph_line_frame(
    graph: nx.Graph,
    *,
    default_voltage_kv: float,
    default_capacity_mva: float,
) -> gpd.GeoDataFrame:
    rows = []
    for number, (bus0, bus1, attrs) in enumerate(graph.edges(data=True), start=1):
        if bus0 == bus1:
            continue
        node0 = graph.nodes[bus0]
        rows.append(
            {
                "line_id": str(attrs.get("edge_id") or f"inferred_line_{number:06d}"),
                "bus0": bus0,
                "bus1": bus1,
                "v_nom_kv": default_voltage_kv,
                "length_km": max(float(attrs.get("length_km", 0.0)), 0.001),
                "s_nom_mva": default_capacity_mva,
                "inferred": True,
                "source": attrs.get("source"),
                "stage": attrs.get("stage", "connectivity_only"),
                "geometry": Point(float(node0["x"]), float(node0["y"])),
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=METRIC_CRS).to_crs("EPSG:4326")


def _inferred_service_weights(
    graph: nx.Graph,
    reviewed_weights: pd.DataFrame,
    bus_frame: gpd.GeoDataFrame,
) -> pd.DataFrame:
    weights = pd.Series(0.0, index=bus_frame["bus_id"].astype(str))
    reviewed = reviewed_weights.set_index("bus_id")["service_weight"]
    for bus_id, weight in reviewed.items():
        bus_node = f"bus::{bus_id}"
        if bus_node not in graph:
            continue
        demand_node = bus_node
        for neighbour in graph.neighbors(bus_node):
            edge = graph.edges[bus_node, neighbour]
            if edge.get("source") == "substation_anchor":
                demand_node = neighbour
                break
        if demand_node in weights.index:
            weights.loc[demand_node] += float(weight)

    total = float(weights.sum())
    if total == 0:
        weights.loc[:] = 1 / len(weights)
    else:
        weights = weights / total
    return pd.DataFrame({"bus_id": weights.index, "service_weight": weights.values})


def _fallback_pypsa_earth_osm_lines() -> Path | None:
    path = (
        Path.cwd()
        / "pypsa-earth"
        / "resources"
        / "mauritius-year-1"
        / "base_network"
        / "all_lines_build_network.geojson"
    )
    return path if path.exists() else None


def _build_inferred_network(
    *,
    input_dir: Path,
    output_dir: Path,
    network_path: Path,
    metadata_path: Path,
    gridfinder_lines_path: Path | None,
    osm_distribution_lines_path: Path | None,
    allow_pypsa_earth_osm_fallback: bool,
    allow_provisional_demand: bool,
    max_anchor_distance_m: float,
    inferred_voltage_kv: float,
    inferred_capacity_mva: float,
    value_of_lost_load: float,
) -> NetworkBuildOutputs:
    substations_path = input_dir / "snapped_substations.parquet"
    service_weights_path = input_dir / "service_weights.csv"
    if not substations_path.exists() or not service_weights_path.exists():
        raise FileNotFoundError(
            "Inferred network build requires snapped_substations.parquet and "
            "service_weights.csv from prepare-assets."
        )

    fallback_path = None
    gridfinder_lines = _read_optional_vector(gridfinder_lines_path)
    osm_distribution_lines = _read_optional_vector(osm_distribution_lines_path)
    if gridfinder_lines is None and osm_distribution_lines is None and allow_pypsa_earth_osm_fallback:
        fallback_path = _fallback_pypsa_earth_osm_lines()
        osm_distribution_lines = _read_optional_vector(fallback_path)

    if gridfinder_lines is None and osm_distribution_lines is None:
        raise FileNotFoundError(
            "No GridFinder, OSM distribution, or PyPSA-Earth OSM line file is available."
        )

    substations = gpd.read_parquet(substations_path)
    graph = build_inferred_distribution_graph(
        substations,
        gridfinder_lines=gridfinder_lines,
        osm_distribution_lines=osm_distribution_lines,
        max_anchor_distance_m=max_anchor_distance_m,
    )
    inferred_tables = write_inferred_distribution_tables(
        graph,
        output_dir / "inferred_distribution",
    )

    buses = _node_bus_frame(graph)
    lines = _graph_line_frame(
        graph,
        default_voltage_kv=inferred_voltage_kv,
        default_capacity_mva=inferred_capacity_mva,
    )
    generators = _load_generators(input_dir, inferred_bus_ids=True)
    demand = _load_demand_profile(input_dir, allow_provisional_demand=allow_provisional_demand)
    reviewed_weights = pd.read_csv(service_weights_path)
    service_weights = _inferred_service_weights(graph, reviewed_weights, buses)

    network = build_operational_network(
        buses,
        lines,
        generators,
        demand,
        service_weights,
        value_of_lost_load=value_of_lost_load,
    )
    _write_network(network_path, network)
    _write_metadata(
        metadata_path,
        {
            "source": "inferred",
            "input_dir": str(input_dir),
            "network": str(network_path),
            "snapshots": len(network.snapshots),
            "buses": len(network.buses),
            "lines": len(network.lines),
            "generators": int(
                network.generators.carrier.ne("load_shedding").sum()
            ),
            "loads": len(network.loads),
            "inferred": True,
            "stage": "connectivity_only",
            "gridfinder_lines_path": str(gridfinder_lines_path)
            if gridfinder_lines_path
            else None,
            "osm_distribution_lines_path": str(osm_distribution_lines_path)
            if osm_distribution_lines_path
            else None,
            "pypsa_earth_osm_fallback": str(fallback_path) if fallback_path else None,
            "allow_provisional_demand": allow_provisional_demand,
            "inferred_voltage_kv": inferred_voltage_kv,
            "inferred_capacity_mva": inferred_capacity_mva,
            "max_anchor_distance_m": max_anchor_distance_m,
        },
    )
    return NetworkBuildOutputs(
        network=network_path,
        metadata=metadata_path,
        inferred_nodes=inferred_tables.nodes,
        inferred_edges=inferred_tables.edges,
        inferred_metadata=inferred_tables.metadata,
    )


def build_network(
    source: str,
    *,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    generator_availability_path: Path | None = None,
    gridfinder_lines_path: Path | None = None,
    osm_distribution_lines_path: Path | None = None,
    allow_pypsa_earth_osm_fallback: bool = True,
    allow_provisional_demand: bool = False,
    max_anchor_distance_m: float = 500,
    inferred_voltage_kv: float = 11,
    inferred_capacity_mva: float = 5,
    value_of_lost_load: float = 10_000,
) -> NetworkBuildOutputs:
    """Build and save a named network-source artifact."""
    source = source.lower()
    input_dir = Path(input_dir or processed_energy_dir() / "collaborator")
    output_dir = Path(output_dir or processed_energy_dir() / "networks")
    network_path = output_dir / f"{source}.nc"
    metadata_path = output_dir / f"{source}_metadata.json"

    if source == "base":
        return _build_base_network(
            input_dir=input_dir,
            network_path=network_path,
            metadata_path=metadata_path,
            generator_availability_path=generator_availability_path,
            value_of_lost_load=value_of_lost_load,
        )
    if source == "inferred":
        return _build_inferred_network(
            input_dir=input_dir,
            output_dir=output_dir,
            network_path=network_path,
            metadata_path=metadata_path,
            gridfinder_lines_path=gridfinder_lines_path
            or incoming_energy_dir() / "gridfinder" / "grid.gpkg",
            osm_distribution_lines_path=osm_distribution_lines_path
            or incoming_energy_dir() / "osm" / "distribution_lines.parquet",
            allow_pypsa_earth_osm_fallback=allow_pypsa_earth_osm_fallback,
            allow_provisional_demand=allow_provisional_demand,
            max_anchor_distance_m=max_anchor_distance_m,
            inferred_voltage_kv=inferred_voltage_kv,
            inferred_capacity_mva=inferred_capacity_mva,
            value_of_lost_load=value_of_lost_load,
        )
    raise ValueError("source must be 'base' or 'inferred'")

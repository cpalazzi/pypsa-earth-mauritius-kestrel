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
from shapely.ops import unary_union

import mu_star_energy.osm as osm
from mu_star_energy.distribution_network import (
    METRIC_CRS,
    build_inferred_distribution_graph,
    write_inferred_distribution_tables,
)
from mu_star_energy.network import assert_fixed_capacity, build_topology_network
from mu_star_energy.paths import incoming_energy_dir, processed_energy_dir

BASE_REQUIRED_FILES = (
    "snapped_substations.parquet",
    "lines.csv",
    "generators.csv",
    "service_weights.csv",
)


@dataclass(frozen=True)
class NetworkBuildOutputs:
    network: Path
    metadata: Path
    inferred_nodes: Path | None = None
    inferred_edges: Path | None = None
    inferred_metadata: Path | None = None


def _coerce_vector_fetch_result(result: object) -> gpd.GeoDataFrame | None:
    if isinstance(result, gpd.GeoDataFrame):
        return result
    path = getattr(result, "path", result)
    if path is None:
        return None
    return _read_optional_vector(Path(path))


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
    service_weights = pd.read_csv(input_dir / "service_weights.csv")
    return buses, lines, generators, service_weights


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
) -> NetworkBuildOutputs:
    buses, lines, generators, _service_weights = _load_reviewed_inputs(input_dir)
    network = build_topology_network(buses, lines, generators)
    _write_network(network_path, network)
    _write_metadata(
        metadata_path,
        {
            "source": "base",
            "input_dir": str(input_dir),
            "network": str(network_path),
            "has_demand": False,
            "snapshots": 0,
            "buses": len(network.buses),
            "lines": len(network.lines),
            "generators": len(network.generators),
            "loads": 0,
            "inferred": False,
        },
    )
    return NetworkBuildOutputs(network=network_path, metadata=metadata_path)


def provisional_demand_profile(input_dir: Path) -> pd.DataFrame:
    path = input_dir / "monthly_peak_demand_mw.csv"
    if not path.exists():
        raise FileNotFoundError(
            "monthly_peak_demand_mw.csv is missing; supply a reviewed demand "
            "profile or place the monthly peak table in this input directory."
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
    columns = [
        "line_id",
        "bus0",
        "bus1",
        "v_nom_kv",
        "length_km",
        "s_nom_mva",
        "inferred",
        "source",
        "stage",
        "geometry",
    ]
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
    return gpd.GeoDataFrame(
        rows,
        columns=columns,
        geometry="geometry",
        crs=METRIC_CRS,
    ).to_crs("EPSG:4326")


def _equal_service_weights(bus_frame: gpd.GeoDataFrame) -> pd.DataFrame:
    bus_ids = bus_frame["bus_id"].astype(str)
    if bus_ids.empty:
        return pd.DataFrame(columns=["bus_id", "service_weight"])
    return pd.DataFrame(
        {
            "bus_id": bus_ids,
            "service_weight": [1 / len(bus_ids)] * len(bus_ids),
        }
    )


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


def _largest_road_component_centroid(roads: gpd.GeoDataFrame | None) -> Point:
    if roads is None or roads.empty:
        return Point(0.0, 0.0)

    prepared = roads.to_crs(METRIC_CRS).explode(index_parts=False).copy()
    prepared = prepared[prepared.geometry.geom_type.eq("LineString")]
    if prepared.empty:
        return Point(0.0, 0.0)

    road_graph = nx.Graph()
    for row in prepared.itertuples():
        coords = list(row.geometry.coords)
        start = (round(float(coords[0][0]), 1), round(float(coords[0][1]), 1))
        end = (round(float(coords[-1][0]), 1), round(float(coords[-1][1]), 1))
        if start == end:
            continue
        road_graph.add_edge(
            start,
            end,
            geometry=row.geometry,
            length=float(row.geometry.length),
        )
    if road_graph.number_of_edges() == 0:
        centroid = unary_union(list(prepared.geometry)).centroid
    else:
        component = max(
            nx.connected_components(road_graph),
            key=lambda nodes: road_graph.subgraph(nodes).size(weight="length"),
        )
        component_lines = [
            attrs["geometry"]
            for start, end, attrs in road_graph.edges(data=True)
            if start in component and end in component
        ]
        centroid = unary_union(component_lines).centroid

    return gpd.GeoSeries([centroid], crs=METRIC_CRS).to_crs("EPSG:4326").iloc[0]


def _normalise_power_substations(
    power_features: gpd.GeoDataFrame | None,
    *,
    island: str,
) -> gpd.GeoDataFrame:
    if power_features is None or power_features.empty:
        return gpd.GeoDataFrame(
            {"bus_id": [], "source": [], "provisional_root": [], "geometry": []},
            geometry="geometry",
            crs="EPSG:4326",
        )

    substations = power_features.copy()
    if substations.crs is None:
        substations = substations.set_crs("EPSG:4326")
    if "bus_id" not in substations.columns:
        substations["bus_id"] = [
            f"{island.upper()}_SUB_{number:03d}"
            for number in range(1, len(substations) + 1)
        ]
    metric = substations.to_crs(METRIC_CRS)
    geometry = metric.geometry
    non_points = ~geometry.geom_type.eq("Point")
    if non_points.any():
        geometry = geometry.copy()
        geometry.loc[non_points] = geometry.loc[non_points].centroid
    return gpd.GeoDataFrame(
        {
            "bus_id": substations["bus_id"].astype(str).to_numpy(),
            "source": substations["source"].astype(str).to_numpy()
            if "source" in substations
            else ["osm_power"] * len(substations),
            "provisional_root": [False] * len(substations),
        },
        geometry=geometry,
        crs=METRIC_CRS,
    ).to_crs("EPSG:4326")


def _provisional_root_substation(island: str, roads: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    centroid = _largest_road_component_centroid(roads)
    return gpd.GeoDataFrame(
        {
            "bus_id": [f"{island.upper()}_SUB_001"],
            "source": ["provisional_road_centroid"],
            "provisional_root": [True],
            "geometry": [centroid],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )


def _inferred_table_dir(output_dir: Path, island: str | None) -> Path:
    if island is None:
        return output_dir / "inferred_distribution"
    return output_dir / f"inferred_distribution-{island}"


def _substation_anchor_counts(graph: nx.Graph) -> tuple[int, int]:
    statuses = [
        attrs.get("anchor_status")
        for _, attrs in graph.nodes(data=True)
        if attrs.get("kind") == "substation"
    ]
    return statuses.count("anchored"), statuses.count("unanchored")


def _build_inferred_network(
    *,
    input_dir: Path,
    output_dir: Path,
    network_path: Path,
    metadata_path: Path,
    island: str | None,
    gridfinder_lines_path: Path | None,
    osm_distribution_lines_path: Path | None,
    allow_pypsa_earth_osm_fallback: bool,
    max_anchor_distance_m: float,
    inferred_voltage_kv: float,
    inferred_capacity_mva: float,
) -> NetworkBuildOutputs:
    fallback_path = None
    provisional_root = False
    if island is not None:
        roads_result = osm.fetch_osm_roads(island)
        osm_distribution_lines = _coerce_vector_fetch_result(roads_result)
        power_result = osm.fetch_osm_power_features(island)
        substations = _normalise_power_substations(
            _coerce_vector_fetch_result(power_result),
            island=island,
        )
        if substations.empty:
            substations = _provisional_root_substation(island, osm_distribution_lines)
            provisional_root = True
        gridfinder_lines = None
        generators = _empty_generators()
    else:
        substations_path = input_dir / "snapped_substations.parquet"
        service_weights_path = input_dir / "service_weights.csv"
        if not substations_path.exists() or not service_weights_path.exists():
            raise FileNotFoundError(
                "Inferred network build requires snapped_substations.parquet and "
                "service_weights.csv from prepare-assets."
            )

        gridfinder_lines = _read_optional_vector(gridfinder_lines_path)
        osm_distribution_lines = _read_optional_vector(osm_distribution_lines_path)
        if (
            gridfinder_lines is None
            and osm_distribution_lines is None
            and allow_pypsa_earth_osm_fallback
        ):
            fallback_path = _fallback_pypsa_earth_osm_lines()
            osm_distribution_lines = _read_optional_vector(fallback_path)

        if gridfinder_lines is None and osm_distribution_lines is None:
            raise FileNotFoundError(
                "No GridFinder, OSM distribution, or PyPSA-Earth OSM line file is available."
            )
        substations = gpd.read_parquet(substations_path)
        generators = _load_generators(input_dir, inferred_bus_ids=True)

    graph = build_inferred_distribution_graph(
        substations,
        gridfinder_lines=gridfinder_lines,
        osm_distribution_lines=osm_distribution_lines,
        max_anchor_distance_m=max_anchor_distance_m,
    )
    table_dir = _inferred_table_dir(output_dir, island)
    inferred_tables = write_inferred_distribution_tables(
        graph,
        table_dir,
    )

    buses = _node_bus_frame(graph)
    lines = _graph_line_frame(
        graph,
        default_voltage_kv=inferred_voltage_kv,
        default_capacity_mva=inferred_capacity_mva,
    )
    if island is None:
        reviewed_weights = pd.read_csv(service_weights_path)
        service_weights = _inferred_service_weights(graph, reviewed_weights, buses)
    else:
        service_weights = _equal_service_weights(buses)
    service_weights_path_out = table_dir / "service_weights.csv"
    service_weights.to_csv(service_weights_path_out, index=False)

    network = build_topology_network(buses, lines, generators)
    anchored, unanchored = _substation_anchor_counts(graph)
    _write_network(network_path, network)
    _write_metadata(
        metadata_path,
        {
            "source": "inferred",
            "input_dir": str(input_dir),
            "network": str(network_path),
            "island": island,
            "has_demand": False,
            "snapshots": 0,
            "buses": len(network.buses),
            "lines": len(network.lines),
            "generators": len(network.generators),
            "loads": 0,
            "inferred": True,
            "stage": "connectivity_only",
            "gridfinder_lines_path": str(gridfinder_lines_path)
            if gridfinder_lines_path
            else None,
            "osm_distribution_lines_path": str(osm_distribution_lines_path)
            if osm_distribution_lines_path
            else None,
            "pypsa_earth_osm_fallback": str(fallback_path) if fallback_path else None,
            "service_weights": str(service_weights_path_out),
            "road_edges": len(osm_distribution_lines)
            if osm_distribution_lines is not None
            else 0,
            "anchored_substations": anchored,
            "unanchored_substations": unanchored,
            "provisional_root": provisional_root,
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
    island: str | None = None,
    gridfinder_lines_path: Path | None = None,
    osm_distribution_lines_path: Path | None = None,
    allow_pypsa_earth_osm_fallback: bool = True,
    max_anchor_distance_m: float = 500,
    inferred_voltage_kv: float = 11,
    inferred_capacity_mva: float = 5,
) -> NetworkBuildOutputs:
    """Build and save a named network-source artifact."""
    source = source.lower()
    if island is not None:
        island = island.lower()
        if source != "inferred":
            raise ValueError("island can only be used with source='inferred'")
        if island not in osm.ISLANDS:
            raise ValueError(f"Unknown island {island!r}; choose from {sorted(osm.ISLANDS)}")
    input_dir = Path(input_dir or processed_energy_dir() / "provided")
    output_dir = Path(output_dir or processed_energy_dir() / "networks")
    output_stem = f"{source}-{island}" if island is not None else source
    network_path = output_dir / f"{output_stem}.nc"
    metadata_path = output_dir / f"{output_stem}_metadata.json"

    if source == "base":
        return _build_base_network(
            input_dir=input_dir,
            network_path=network_path,
            metadata_path=metadata_path,
        )
    if source == "inferred":
        return _build_inferred_network(
            input_dir=input_dir,
            output_dir=output_dir,
            network_path=network_path,
            metadata_path=metadata_path,
            island=island,
            gridfinder_lines_path=gridfinder_lines_path
            or incoming_energy_dir() / "gridfinder" / "grid.gpkg",
            osm_distribution_lines_path=osm_distribution_lines_path
            or incoming_energy_dir() / "osm" / "distribution_lines.parquet",
            allow_pypsa_earth_osm_fallback=allow_pypsa_earth_osm_fallback,
            max_anchor_distance_m=max_anchor_distance_m,
            inferred_voltage_kv=inferred_voltage_kv,
            inferred_capacity_mva=inferred_capacity_mva,
        )
    raise ValueError("source must be 'base' or 'inferred'")

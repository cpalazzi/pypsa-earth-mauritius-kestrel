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
from mu_star_energy.base_topology import derive_base_topology
from mu_star_energy.distribution_network import (
    METRIC_CRS,
    build_inferred_distribution_graph,
    write_inferred_distribution_tables,
)
from mu_star_energy.network import assert_fixed_capacity, build_topology_network
from mu_star_energy.network_tables import (
    CEB_REPORTED_INSTALLED_GENERATION_MW,
    CEB_TRANSMISSION_LENGTH_KM,
    GENERATOR_REQUIRED_COLUMNS,
    validate_model_tables,
    write_model_tables,
)
from mu_star_energy.paths import incoming_energy_dir, processed_energy_dir

BASE_REQUIRED_FILES = (
    "snapped_substations.parquet",
    "transmission_routes.parquet",
    "generators.csv",
)


@dataclass(frozen=True)
class NetworkBuildOutputs:
    network: Path
    metadata: Path
    inferred_nodes: Path | None = None
    inferred_edges: Path | None = None
    inferred_metadata: Path | None = None
    generators: Path | None = None
    lines: Path | None = None
    validation: Path | None = None


def _coerce_vector_fetch_result(result: object) -> gpd.GeoDataFrame | None:
    if isinstance(result, gpd.GeoDataFrame):
        return result
    path = getattr(result, "path", result)
    if path is None:
        return None
    return _read_optional_vector(Path(path))


def _coerce_optional_vector(
    value: gpd.GeoDataFrame | str | Path | None,
) -> gpd.GeoDataFrame | None:
    if isinstance(value, gpd.GeoDataFrame):
        return value
    if value is None:
        return None
    return _read_optional_vector(Path(value))


def _read_optional_vector(path: Path | None) -> gpd.GeoDataFrame | None:
    if path is None or not path.exists():
        return None
    if path.suffix.lower() == ".parquet":
        return gpd.read_parquet(path)
    return gpd.read_file(path)


def _missing_files(input_dir: Path, names: tuple[str, ...]) -> list[Path]:
    return [input_dir / name for name in names if not (input_dir / name).exists()]


def _load_reviewed_inputs(
    input_dir: Path,
) -> tuple[
    gpd.GeoDataFrame,
    gpd.GeoDataFrame,
    pd.DataFrame,
]:
    missing = _missing_files(input_dir, BASE_REQUIRED_FILES)
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            f"Cannot build the base network until these prepared files exist:\n{formatted}"
        )

    buses = gpd.read_parquet(input_dir / "snapped_substations.parquet")
    routes = gpd.read_parquet(input_dir / "transmission_routes.parquet")
    generators = pd.read_csv(input_dir / "generators.csv")
    return buses, routes, generators


def _complete_generators(generators: pd.DataFrame) -> pd.DataFrame:
    complete = generators[list(GENERATOR_REQUIRED_COLUMNS)].notna().all(axis=1)
    return generators.loc[complete].copy()


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
    table_output_dir: Path | None,
    reference_line_length_km: float,
    line_length_tolerance_fraction: float,
    reference_generation_capacity_mw: float,
    generation_capacity_tolerance_fraction: float,
    route_gap_tolerance_m: float,
    default_voltage_kv: float,
    topology_capacity_mva: float,
) -> NetworkBuildOutputs:
    snapped_substations, transmission_routes, generators = _load_reviewed_inputs(input_dir)
    topology = derive_base_topology(
        snapped_substations,
        transmission_routes,
        route_gap_tolerance_m=route_gap_tolerance_m,
        default_voltage_kv=default_voltage_kv,
        topology_capacity_mva=topology_capacity_mva,
    )
    buses = topology.buses
    lines = topology.lines
    table_outputs = None
    if table_output_dir is None:
        validation = validate_model_tables(
            buses,
            lines,
            generators,
            source="base",
            reference_line_length_km=reference_line_length_km,
            line_length_tolerance_fraction=line_length_tolerance_fraction,
            reference_generation_capacity_mw=reference_generation_capacity_mw,
            generation_capacity_tolerance_fraction=(generation_capacity_tolerance_fraction),
            allow_incomplete_generators=True,
        )
    else:
        table_outputs, validation = write_model_tables(
            buses,
            lines,
            generators,
            table_output_dir,
            source="base",
            reference_line_length_km=reference_line_length_km,
            line_length_tolerance_fraction=line_length_tolerance_fraction,
            reference_generation_capacity_mw=reference_generation_capacity_mw,
            generation_capacity_tolerance_fraction=(generation_capacity_tolerance_fraction),
            allow_incomplete_generators=True,
        )
    if validation["errors"]:
        raise ValueError("Invalid base network tables:\n- " + "\n- ".join(validation["errors"]))
    network_generators = _complete_generators(generators)
    network = build_topology_network(buses, lines, network_generators)
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
            "generator_records": len(generators),
            "generator_output_capacity_mw": float(network.generators.p_nom.sum()),
            "loads": 0,
            "inferred": False,
            "derived": True,
            "stage": "topology_only",
            "substations": topology.substation_count,
            "junctions": topology.junction_count,
            "connected_components": topology.connected_components,
            "route_gap_connectors": topology.route_gap_count,
            "route_gap_length_km": topology.route_gap_length_km,
            "route_gap_tolerance_m": route_gap_tolerance_m,
            "default_voltage_kv": default_voltage_kv,
            "topology_capacity_mva": topology_capacity_mva,
            "human_tables": str(table_output_dir) if table_output_dir else None,
            "validation_status": validation["status"],
            "validation_warnings": validation["warnings"],
        },
    )
    return NetworkBuildOutputs(
        network=network_path,
        metadata=metadata_path,
        generators=table_outputs.generators if table_outputs else None,
        lines=table_outputs.lines if table_outputs else None,
        validation=table_outputs.validation if table_outputs else None,
    )


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
            "output_capacity_mw",
            "capacity_basis",
            "marginal_cost",
        ]
    )


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
    region: str,
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
            f"{region.upper()}_SUB_{number:03d}" for number in range(1, len(substations) + 1)
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


def _provisional_root_substation(region: str, roads: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    centroid = _largest_road_component_centroid(roads)
    return gpd.GeoDataFrame(
        {
            "bus_id": [f"{region.upper()}_SUB_001"],
            "source": ["provisional_road_centroid"],
            "provisional_root": [True],
            "geometry": [centroid],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )


def _default_gridfinder_lines_path() -> Path:
    return incoming_energy_dir() / "gridfinder" / "grid.gpkg"


def _inferred_table_dir(output_dir: Path, output_stem: str) -> Path:
    if output_stem == "inferred":
        return output_dir / "inferred_distribution"
    if output_stem.startswith("inferred-"):
        suffix = output_stem.removeprefix("inferred-")
        return output_dir / f"inferred_distribution-{suffix}"
    return output_dir / f"{output_stem}_inferred_distribution"


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
    output_stem: str,
    network_path: Path,
    metadata_path: Path,
    region: str,
    allow_download: bool,
    network_type: str,
    gridfinder_lines: gpd.GeoDataFrame | str | Path | None,
    max_anchor_distance_m: float,
    inferred_voltage_kv: float,
    inferred_capacity_mva: float,
    table_output_dir: Path | None,
    line_length_tolerance_fraction: float,
) -> NetworkBuildOutputs:
    provisional_root = False
    roads_result = osm.fetch_osm_roads(
        region, network_type=network_type, allow_download=allow_download
    )
    osm_distribution_lines = _coerce_vector_fetch_result(roads_result)
    try:
        power_result = osm.fetch_osm_power_features(
            region,
            allow_download=allow_download,
        )
    except osm.OSMDownloadRequired:
        power_result = None
    substations = _normalise_power_substations(
        _coerce_vector_fetch_result(power_result),
        region=region,
    )
    if substations.empty:
        substations = _provisional_root_substation(region, osm_distribution_lines)
        provisional_root = True

    if gridfinder_lines is None:
        gridfinder_lines_path = _default_gridfinder_lines_path()
        gridfinder_distribution_lines = _read_optional_vector(gridfinder_lines_path)
    else:
        gridfinder_lines_path = (
            Path(gridfinder_lines) if isinstance(gridfinder_lines, (str, Path)) else None
        )
        gridfinder_distribution_lines = _coerce_optional_vector(gridfinder_lines)

    graph = build_inferred_distribution_graph(
        substations,
        gridfinder_lines=gridfinder_distribution_lines,
        osm_distribution_lines=osm_distribution_lines,
        max_anchor_distance_m=max_anchor_distance_m,
    )
    table_dir = _inferred_table_dir(output_dir, output_stem)
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
    service_weights = _equal_service_weights(buses)
    service_weights_path_out = table_dir / "service_weights.csv"
    service_weights.to_csv(service_weights_path_out, index=False)

    generators = _empty_generators()
    table_outputs = None
    if table_output_dir is None:
        validation = validate_model_tables(
            buses,
            lines,
            generators,
            source="inferred",
            line_length_tolerance_fraction=line_length_tolerance_fraction,
        )
    else:
        table_outputs, validation = write_model_tables(
            buses,
            lines,
            generators,
            table_output_dir,
            source="inferred",
            line_length_tolerance_fraction=line_length_tolerance_fraction,
        )
    if validation["errors"]:
        raise ValueError("Invalid inferred network tables:\n- " + "\n- ".join(validation["errors"]))
    network = build_topology_network(buses, lines, generators)
    anchored, unanchored = _substation_anchor_counts(graph)
    _write_network(network_path, network)
    _write_metadata(
        metadata_path,
        {
            "source": "inferred",
            "input_dir": str(input_dir),
            "network": str(network_path),
            "region": region,
            "network_type": network_type,
            "has_demand": False,
            "snapshots": 0,
            "buses": len(network.buses),
            "lines": len(network.lines),
            "generators": len(network.generators),
            "loads": 0,
            "inferred": True,
            "stage": "connectivity_only",
            "service_weights": str(service_weights_path_out),
            "road_edges": len(osm_distribution_lines) if osm_distribution_lines is not None else 0,
            "gridfinder_edges": len(gridfinder_distribution_lines)
            if gridfinder_distribution_lines is not None
            else 0,
            "gridfinder_lines_path": str(gridfinder_lines_path)
            if gridfinder_lines_path is not None
            else None,
            "anchored_substations": anchored,
            "unanchored_substations": unanchored,
            "provisional_root": provisional_root,
            "inferred_voltage_kv": inferred_voltage_kv,
            "inferred_capacity_mva": inferred_capacity_mva,
            "max_anchor_distance_m": max_anchor_distance_m,
            "human_tables": str(table_output_dir) if table_output_dir else None,
            "validation_status": validation["status"],
            "validation_warnings": validation["warnings"],
        },
    )
    return NetworkBuildOutputs(
        network=network_path,
        metadata=metadata_path,
        inferred_nodes=inferred_tables.nodes,
        inferred_edges=inferred_tables.edges,
        inferred_metadata=inferred_tables.metadata,
        generators=table_outputs.generators if table_outputs else None,
        lines=table_outputs.lines if table_outputs else None,
        validation=table_outputs.validation if table_outputs else None,
    )


def build_network(
    source: str,
    *,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    region: str | None = None,
    output_name: str | None = None,
    overwrite: bool = False,
    allow_download: bool = False,
    network_type: str = "drive",
    gridfinder_lines: gpd.GeoDataFrame | str | Path | None = None,
    max_anchor_distance_m: float = 500,
    inferred_voltage_kv: float = 11,
    inferred_capacity_mva: float = 5,
    export_root: Path | None = None,
    reference_line_length_km: float = CEB_TRANSMISSION_LENGTH_KM,
    line_length_tolerance_fraction: float = 0.35,
    reference_generation_capacity_mw: float = CEB_REPORTED_INSTALLED_GENERATION_MW,
    generation_capacity_tolerance_fraction: float = 0.10,
    base_route_gap_tolerance_m: float = 75,
    base_default_voltage_kv: float = 66,
    base_topology_capacity_mva: float = 10_000,
) -> NetworkBuildOutputs:
    """Build and save a named network-source artifact.

    ``source="base"`` derives a topology from prepared provided-data geometry.
    ``source="inferred"``
    requires a ``region`` (any OSM/Nominatim query, e.g. "Rodrigues, Mauritius")
    and builds the topology from that region's OSM roads plus an optional local
    GridFinder line layer. OSM power features are used as substation roots when
    cached; otherwise a provisional road-network root is created. Existing
    outputs are not overwritten unless ``overwrite`` is set, and OSM data is
    only downloaded when ``allow_download`` is True. When ``export_root`` is
    supplied, the human-readable ``generators.csv``, ``lines.csv`` and
    validation report are written below a source-named subdirectory.
    """
    source = source.lower()
    if source not in {"base", "inferred"}:
        raise ValueError("source must be 'base' or 'inferred'")
    if region is not None and source != "inferred":
        raise ValueError("region can only be used with source='inferred'")
    if source == "inferred" and not region:
        raise ValueError(
            "source='inferred' requires a region, e.g. region='Rodrigues, Mauritius' "
            "or a REGIONS shortcut like 'rodrigues'."
        )

    input_dir = Path(input_dir or processed_energy_dir() / "provided")
    output_dir = Path(output_dir or processed_energy_dir() / "networks")
    if output_name:
        output_stem = output_name
    elif source == "inferred":
        output_stem = f"inferred-{osm.region_slug(region)}"
    else:
        output_stem = "base"
    network_path = output_dir / f"{output_stem}.nc"
    metadata_path = output_dir / f"{output_stem}_metadata.json"
    table_output_dir = Path(export_root) / output_stem if export_root else None

    if network_path.exists() and not overwrite:
        raise FileExistsError(
            f"{network_path} already exists; set overwrite=True (notebook: OVERWRITE = True) "
            "or pass a different output_name to rebuild it."
        )

    if source == "base":
        return _build_base_network(
            input_dir=input_dir,
            network_path=network_path,
            metadata_path=metadata_path,
            table_output_dir=table_output_dir,
            reference_line_length_km=reference_line_length_km,
            line_length_tolerance_fraction=line_length_tolerance_fraction,
            reference_generation_capacity_mw=reference_generation_capacity_mw,
            generation_capacity_tolerance_fraction=(generation_capacity_tolerance_fraction),
            route_gap_tolerance_m=base_route_gap_tolerance_m,
            default_voltage_kv=base_default_voltage_kv,
            topology_capacity_mva=base_topology_capacity_mva,
        )
    return _build_inferred_network(
        input_dir=input_dir,
        output_dir=output_dir,
        output_stem=output_stem,
        network_path=network_path,
        metadata_path=metadata_path,
        region=region,
        allow_download=allow_download,
        network_type=network_type,
        gridfinder_lines=gridfinder_lines,
        max_anchor_distance_m=max_anchor_distance_m,
        inferred_voltage_kv=inferred_voltage_kv,
        inferred_capacity_mva=inferred_capacity_mva,
        table_output_dir=table_output_dir,
        line_length_tolerance_fraction=line_length_tolerance_fraction,
    )

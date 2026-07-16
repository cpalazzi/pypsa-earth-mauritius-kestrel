"""Derive the base transmission topology from provided route geometry."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, substring, unary_union

METRIC_CRS = "EPSG:32740"


@dataclass(frozen=True)
class DerivedBaseTopology:
    buses: gpd.GeoDataFrame
    lines: gpd.GeoDataFrame
    route_gap_count: int
    route_gap_length_km: float
    connected_components: int
    substation_count: int
    junction_count: int


def _require_columns(
    frame: pd.DataFrame,
    columns: set[str],
    label: str,
) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns: {sorted(missing)}")


def _segments(geometry) -> list[LineString]:
    if geometry.geom_type == "LineString":
        return [geometry]
    return [part for part in geometry.geoms if part.geom_type == "LineString"]


def _node_key(coordinate: tuple[float, ...]) -> tuple[float, float]:
    return round(float(coordinate[0]), 3), round(float(coordinate[1]), 3)


def _linework_graph(linework) -> nx.Graph:
    graph = nx.Graph()
    for segment in _segments(linework):
        coordinates = list(segment.coords)
        graph.add_edge(
            _node_key(coordinates[0]),
            _node_key(coordinates[-1]),
            geometry=segment,
        )
    return graph


def _component_geometries(linework) -> list:
    graph = _linework_graph(linework)
    return [
        unary_union([attrs["geometry"] for _, _, attrs in graph.subgraph(nodes).edges(data=True)])
        for nodes in nx.connected_components(graph)
    ]


def _route_gap_connectors(linework, tolerance_m: float) -> list[LineString]:
    if tolerance_m < 0:
        raise ValueError("route_gap_tolerance_m must be non-negative")
    components = _component_geometries(linework)
    connectors: list[LineString] = []
    for index, first in enumerate(components):
        for second in components[index + 1 :]:
            distance = float(first.distance(second))
            if not 0.001 < distance <= tolerance_m:
                continue
            start, end = nearest_points(first, second)
            connectors.append(LineString([start, end]))
    return connectors


def _prepared_route_parts(routes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    parts = routes.to_crs(METRIC_CRS).explode(index_parts=False).reset_index(drop=True)
    parts = parts[parts.geometry.geom_type.eq("LineString")].copy()
    if parts.empty:
        raise ValueError("transmission_routes has no LineString geometry")
    parts["route_part_id"] = [
        f"{route_id}_PART_{number:03d}"
        for route_id, number in zip(
            parts["route_id"],
            parts.groupby("route_id").cumcount() + 1,
            strict=True,
        )
    ]
    return parts


def _segment_source(
    segment: LineString,
    route_parts: gpd.GeoDataFrame,
    gap_connectors: list[LineString],
    *,
    default_voltage_kv: float,
) -> dict[str, object]:
    midpoint = segment.interpolate(0.5, normalized=True)
    route_distances = route_parts.geometry.distance(midpoint)
    route_index = route_distances.idxmin()
    route_distance = float(route_distances.loc[route_index])
    gap_distance = (
        min(float(connector.distance(midpoint)) for connector in gap_connectors)
        if gap_connectors
        else float("inf")
    )
    if gap_distance < 0.01 and route_distance >= 0.01:
        return {
            "source": "derived_route_gap",
            "source_route_id": pd.NA,
            "source_route_part_id": pd.NA,
            "v_nom_kv": default_voltage_kv,
        }

    route = route_parts.loc[route_index]
    voltage = route.get("v_nom_kv", default_voltage_kv)
    if pd.isna(voltage):
        voltage = default_voltage_kv
    return {
        "source": "provided_transmission_geometry",
        "source_route_id": str(route["route_id"]),
        "source_route_part_id": str(route["route_part_id"]),
        "v_nom_kv": float(voltage),
    }


def _split_graph_at_substations(
    linework,
    substations: gpd.GeoDataFrame,
    route_parts: gpd.GeoDataFrame,
    gap_connectors: list[LineString],
    *,
    default_voltage_kv: float,
) -> tuple[nx.Graph, dict[str, Point]]:
    bus_points = {
        str(row.bus_id): nearest_points(row.geometry, linework)[1]
        for row in substations.itertuples()
    }
    graph = nx.Graph()
    for segment in _segments(linework):
        cut_distances = []
        for point in bus_points.values():
            if segment.distance(point) >= 0.02:
                continue
            distance = float(segment.project(point))
            if 0.02 < distance < segment.length - 0.02:
                cut_distances.append(round(distance, 3))
        distances = [0.0, *sorted(set(cut_distances)), float(segment.length)]
        source = _segment_source(
            segment,
            route_parts,
            gap_connectors,
            default_voltage_kv=default_voltage_kv,
        )
        for start, end in zip(distances[:-1], distances[1:], strict=True):
            if end - start < 0.001:
                continue
            piece = substring(segment, start, end)
            coordinates = list(piece.coords)
            node0 = _node_key(coordinates[0])
            node1 = _node_key(coordinates[-1])
            if node0 == node1:
                continue
            graph.add_edge(
                node0,
                node1,
                geometry=piece,
                length_km=float(piece.length / 1000),
                **source,
            )

    for bus_id, point in bus_points.items():
        node = _node_key((point.x, point.y))
        if node not in graph:
            node = min(
                graph,
                key=lambda candidate: (candidate[0] - point.x) ** 2 + (candidate[1] - point.y) ** 2,
            )
            distance = ((node[0] - point.x) ** 2 + (node[1] - point.y) ** 2) ** 0.5
            if distance > 0.01:
                raise ValueError(f"Could not place {bus_id} on derived route graph")
        existing_bus_id = graph.nodes[node].get("bus_id")
        if existing_bus_id is not None and existing_bus_id != bus_id:
            raise ValueError(f"Substations {existing_bus_id} and {bus_id} occupy one node")
        graph.nodes[node]["bus_id"] = bus_id
    return graph, bus_points


def _prune_unserved_route_ends(graph: nx.Graph) -> None:
    for component in list(nx.connected_components(graph)):
        if not any(graph.nodes[node].get("bus_id") for node in component):
            graph.remove_nodes_from(component)
    while True:
        leaves = [
            node
            for node in graph
            if graph.degree(node) <= 1 and not graph.nodes[node].get("bus_id")
        ]
        if not leaves:
            return
        graph.remove_nodes_from(leaves)


def derive_base_topology(
    snapped_substations: gpd.GeoDataFrame,
    transmission_routes: gpd.GeoDataFrame,
    *,
    route_gap_tolerance_m: float = 75,
    default_voltage_kv: float = 66,
    topology_capacity_mva: float = 10_000,
) -> DerivedBaseTopology:
    """Create a connected, topology-only base network from provided geometry.

    Short gaps between route components are retained as explicit derived
    connectors. Line ratings use a deliberately non-binding topology proxy
    until reviewed engineering ratings are available.
    """
    _require_columns(snapped_substations, {"bus_id", "geometry"}, "substations")
    _require_columns(
        transmission_routes,
        {"route_id", "geometry"},
        "transmission_routes",
    )
    if default_voltage_kv <= 0:
        raise ValueError("default_voltage_kv must be greater than zero")
    if topology_capacity_mva <= 0:
        raise ValueError("topology_capacity_mva must be greater than zero")

    substations = snapped_substations.to_crs(METRIC_CRS).copy()
    route_parts = _prepared_route_parts(transmission_routes)
    original_linework = unary_union(list(route_parts.geometry))
    gap_connectors = _route_gap_connectors(
        original_linework,
        route_gap_tolerance_m,
    )
    linework = unary_union([original_linework, *gap_connectors])
    graph, _bus_points = _split_graph_at_substations(
        linework,
        substations,
        route_parts,
        gap_connectors,
        default_voltage_kv=default_voltage_kv,
    )
    _prune_unserved_route_ends(graph)

    bus_nodes = {
        str(attrs["bus_id"]): node
        for node, attrs in graph.nodes(data=True)
        if attrs.get("bus_id") is not None
    }
    missing_buses = sorted(set(substations["bus_id"].astype(str)) - set(bus_nodes))
    if missing_buses:
        raise ValueError(f"Derived topology omitted substations: {missing_buses}")

    node_ids = {node: bus_id for bus_id, node in bus_nodes.items()}
    junction_nodes = sorted(node for node in graph if node not in node_ids)
    node_ids.update(
        {node: f"JUNCTION_{number:03d}" for number, node in enumerate(junction_nodes, start=1)}
    )

    substation_names = (
        substations.set_index(substations["bus_id"].astype(str))["name"].to_dict()
        if "name" in substations
        else {}
    )
    bus_rows = []
    for node, bus_id in sorted(node_ids.items(), key=lambda item: item[1]):
        is_junction = node not in bus_nodes.values()
        bus_rows.append(
            {
                "bus_id": bus_id,
                "name": bus_id if is_junction else substation_names.get(bus_id, bus_id),
                "kind": "junction" if is_junction else "substation",
                "v_nom_kv": default_voltage_kv,
                "source": "derived_route_junction"
                if is_junction
                else "provided_substation_snapped",
                "geometry": Point(*node),
            }
        )
    buses = gpd.GeoDataFrame(bus_rows, geometry="geometry", crs=METRIC_CRS).to_crs("EPSG:4326")

    line_rows = []
    sorted_edges = sorted(
        graph.edges(data=True),
        key=lambda edge: tuple(sorted((node_ids[edge[0]], node_ids[edge[1]]))),
    )
    for number, (node0, node1, attrs) in enumerate(sorted_edges, start=1):
        line_rows.append(
            {
                "line_id": f"BASE_LINE_{number:03d}",
                "bus0": node_ids[node0],
                "bus1": node_ids[node1],
                "v_nom_kv": float(attrs["v_nom_kv"]),
                "length_km": float(attrs["length_km"]),
                "s_nom_mva": topology_capacity_mva,
                "source_route_id": attrs["source_route_id"],
                "source_route_part_id": attrs["source_route_part_id"],
                "source": attrs["source"],
                "derived": True,
                "inferred": False,
                "stage": "topology_only",
                "rating_basis": "non_binding_topology_proxy",
                "geometry": attrs["geometry"],
            }
        )
    lines = gpd.GeoDataFrame(
        line_rows,
        geometry="geometry",
        crs=METRIC_CRS,
    ).to_crs("EPSG:4326")

    return DerivedBaseTopology(
        buses=buses,
        lines=lines,
        route_gap_count=len(gap_connectors),
        route_gap_length_km=sum(connector.length for connector in gap_connectors) / 1000,
        connected_components=nx.number_connected_components(graph),
        substation_count=len(bus_nodes),
        junction_count=len(junction_nodes),
    )

"""Inferred distribution-network graph experiments.

This module is deliberately separate from the reviewed transmission baseline.
It supports a topology-only scenario: infer candidate feeders from GridFinder
or OSM lines, anchor them to reviewed substations, place proxy demand on graph
nodes and estimate demand disconnected by graph cuts. It does not run
distribution power flow or create confirmed engineering assets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString

METRIC_CRS = "EPSG:32740"


@dataclass(frozen=True)
class InferredDistributionOutputs:
    nodes: Path
    edges: Path
    metadata: Path


def _node_key(x: float, y: float) -> str:
    return f"dist::{round(x, 1)}::{round(y, 1)}"


def _line_endpoints(line: LineString) -> tuple[tuple[float, float], tuple[float, float]]:
    coords = list(line.coords)
    return (float(coords[0][0]), float(coords[0][1])), (
        float(coords[-1][0]),
        float(coords[-1][1]),
    )


def _distribution_nodes(graph: nx.Graph) -> list[str]:
    return [
        node
        for node, attrs in graph.nodes(data=True)
        if attrs.get("kind") == "distribution_node"
    ]


def _nearest_node(
    graph: nx.Graph,
    x: float,
    y: float,
    candidates: list[str],
) -> tuple[str | None, float]:
    if not candidates:
        return None, float("inf")
    distances = {
        node: ((graph.nodes[node]["x"] - x) ** 2 + (graph.nodes[node]["y"] - y) ** 2)
        ** 0.5
        for node in candidates
    }
    node = min(distances, key=distances.get)
    return node, float(distances[node])


def _add_distribution_lines(
    graph: nx.Graph,
    lines: gpd.GeoDataFrame | None,
    *,
    source: str,
) -> None:
    if lines is None or lines.empty:
        return

    prepared = lines.to_crs(METRIC_CRS).explode(index_parts=False).copy()
    prepared = prepared[prepared.geometry.geom_type.eq("LineString")]
    for row_number, row in enumerate(prepared.itertuples(), start=1):
        start, end = _line_endpoints(row.geometry)
        start_node = _node_key(*start)
        end_node = _node_key(*end)
        graph.add_node(
            start_node,
            kind="distribution_node",
            inferred=True,
            source=source,
            x=start[0],
            y=start[1],
            demand_mw=graph.nodes[start_node].get("demand_mw", 0.0)
            if start_node in graph
            else 0.0,
        )
        graph.add_node(
            end_node,
            kind="distribution_node",
            inferred=True,
            source=source,
            x=end[0],
            y=end[1],
            demand_mw=graph.nodes[end_node].get("demand_mw", 0.0)
            if end_node in graph
            else 0.0,
        )
        length_km = float(row.geometry.length / 1000)
        graph.add_edge(
            start_node,
            end_node,
            edge_id=f"{source}_{row_number:06d}",
            source=source,
            inferred=True,
            stage="connectivity_only",
            length_km=length_km,
        )


def build_inferred_distribution_graph(
    substations: gpd.GeoDataFrame,
    *,
    gridfinder_lines: gpd.GeoDataFrame | None = None,
    osm_distribution_lines: gpd.GeoDataFrame | None = None,
    max_anchor_distance_m: float = 500,
) -> nx.Graph:
    """Build a labelled topology-only distribution graph.

    Reviewed substations are added as root nodes. GridFinder and OSM line
    endpoints become inferred distribution nodes. A substation is anchored to
    the nearest distribution node only when it lies within
    ``max_anchor_distance_m``.
    """
    if "bus_id" not in substations.columns:
        raise ValueError("substations must contain bus_id")
    if max_anchor_distance_m < 0:
        raise ValueError("max_anchor_distance_m must be non-negative")

    graph = nx.Graph(
        scenario="inferred_distribution",
        stage="connectivity_only",
        inferred=True,
        max_anchor_distance_m=float(max_anchor_distance_m),
    )
    _add_distribution_lines(graph, gridfinder_lines, source="gridfinder")
    _add_distribution_lines(graph, osm_distribution_lines, source="osm")

    metric_substations = substations.to_crs(METRIC_CRS)
    for row in metric_substations.itertuples():
        bus_id = str(row.bus_id)
        bus_node = f"bus::{bus_id}"
        graph.add_node(
            bus_node,
            kind="substation",
            inferred=False,
            bus_id=bus_id,
            x=float(row.geometry.x),
            y=float(row.geometry.y),
            demand_mw=0.0,
        )

    candidates = _distribution_nodes(graph)
    for row in metric_substations.itertuples():
        bus_id = str(row.bus_id)
        bus_node = f"bus::{bus_id}"
        nearest, distance_m = _nearest_node(
            graph,
            float(row.geometry.x),
            float(row.geometry.y),
            candidates,
        )
        if nearest is None or distance_m > max_anchor_distance_m:
            graph.nodes[bus_node]["anchor_status"] = "unanchored"
            graph.nodes[bus_node]["anchor_distance_m"] = distance_m
            continue
        graph.nodes[bus_node]["anchor_status"] = "anchored"
        graph.nodes[bus_node]["anchor_distance_m"] = distance_m
        graph.add_edge(
            bus_node,
            nearest,
            edge_id=f"anchor::{bus_id}",
            source="substation_anchor",
            inferred=True,
            stage="connectivity_only",
            length_km=distance_m / 1000,
        )
    return graph


def assign_proxy_demand_to_graph(
    graph: nx.Graph,
    demand_points: gpd.GeoDataFrame,
    *,
    demand_column: str = "demand_mw",
) -> nx.Graph:
    """Attach demand proxy values to the nearest inferred distribution node."""
    if demand_column not in demand_points.columns:
        raise ValueError(f"demand_points must contain {demand_column}")
    candidates = _distribution_nodes(graph)
    if not candidates:
        raise ValueError("Cannot assign proxy demand without distribution nodes")

    updated = graph.copy()
    metric_points = demand_points.to_crs(METRIC_CRS)
    for row in metric_points.itertuples():
        demand = float(getattr(row, demand_column))
        if demand < 0:
            raise ValueError("Proxy demand cannot be negative")
        nearest, _ = _nearest_node(
            updated,
            float(row.geometry.x),
            float(row.geometry.y),
            candidates,
        )
        if nearest is None:
            continue
        updated.nodes[nearest]["demand_mw"] = (
            float(updated.nodes[nearest].get("demand_mw", 0.0)) + demand
        )
    return updated


def topology_disconnection_impacts(
    graph: nx.Graph,
    *,
    failed_bus_ids: list[str] | tuple[str, ...] = (),
    failed_edge_ids: list[str] | tuple[str, ...] = (),
) -> pd.DataFrame:
    """Return demand on graph components disconnected from every substation."""
    scenario = graph.copy()
    failed_bus_nodes = {f"bus::{bus_id}" for bus_id in failed_bus_ids}
    scenario.remove_nodes_from(node for node in failed_bus_nodes if node in scenario)

    failed_edges = set(failed_edge_ids)
    edges_to_remove = [
        (u, v)
        for u, v, attrs in scenario.edges(data=True)
        if attrs.get("edge_id") in failed_edges
    ]
    scenario.remove_edges_from(edges_to_remove)

    rows: list[dict[str, object]] = []
    root_nodes = {
        node
        for node, attrs in scenario.nodes(data=True)
        if attrs.get("kind") == "substation"
    }
    for component_id, nodes in enumerate(nx.connected_components(scenario), start=1):
        node_set = set(nodes)
        has_root = bool(node_set & root_nodes)
        demand_mw = sum(
            float(scenario.nodes[node].get("demand_mw", 0.0)) for node in node_set
        )
        if has_root or demand_mw == 0:
            continue
        edge_count = scenario.subgraph(node_set).number_of_edges()
        rows.append(
            {
                "component_id": component_id,
                "unserved_demand_mw": demand_mw,
                "node_count": len(node_set),
                "edge_count": edge_count,
                "inferred": True,
                "stage": "connectivity_only",
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "component_id",
            "unserved_demand_mw",
            "node_count",
            "edge_count",
            "inferred",
            "stage",
        ],
    )


def write_inferred_distribution_tables(
    graph: nx.Graph,
    output_dir: Path,
) -> InferredDistributionOutputs:
    """Write graph nodes, edges and metadata to CSV/JSON review files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = pd.DataFrame(
        [{"node_id": node, **attrs} for node, attrs in graph.nodes(data=True)]
    )
    edges = pd.DataFrame(
        [{"u": u, "v": v, **attrs} for u, v, attrs in graph.edges(data=True)]
    )
    metadata = {
        "scenario": graph.graph.get("scenario"),
        "stage": graph.graph.get("stage"),
        "inferred": graph.graph.get("inferred"),
        "max_anchor_distance_m": graph.graph.get("max_anchor_distance_m"),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }

    node_path = output_dir / "inferred_distribution_nodes.csv"
    edge_path = output_dir / "inferred_distribution_edges.csv"
    metadata_path = output_dir / "inferred_distribution_metadata.json"
    nodes.to_csv(node_path, index=False)
    edges.to_csv(edge_path, index=False)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return InferredDistributionOutputs(
        nodes=node_path,
        edges=edge_path,
        metadata=metadata_path,
    )

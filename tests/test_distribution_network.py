import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.distribution_network import (
    assign_proxy_demand_to_graph,
    build_inferred_distribution_graph,
    topology_disconnection_impacts,
    write_inferred_distribution_tables,
)


def test_inferred_distribution_graph_is_anchored_and_labelled(tmp_path):
    substations = gpd.GeoDataFrame(
        {"bus_id": ["SUB_001"], "geometry": [Point(57.5, -20.2)]},
        crs="EPSG:4326",
    )
    gridfinder = gpd.GeoDataFrame(
        {
            "geometry": [
                LineString([(57.5001, -20.2), (57.501, -20.2)]),
            ]
        },
        crs="EPSG:4326",
    )

    graph = build_inferred_distribution_graph(
        substations,
        gridfinder_lines=gridfinder,
        max_anchor_distance_m=100,
    )
    outputs = write_inferred_distribution_tables(graph, tmp_path)

    assert graph.graph["inferred"] is True
    assert graph.graph["stage"] == "connectivity_only"
    assert graph.nodes["bus::SUB_001"]["anchor_status"] == "anchored"
    assert outputs.nodes.is_file()
    assert outputs.edges.is_file()
    assert outputs.metadata.is_file()


def test_topology_disconnection_counts_only_demand_without_substation_root():
    substations = gpd.GeoDataFrame(
        {"bus_id": ["SUB_001"], "geometry": [Point(57.5, -20.2)]},
        crs="EPSG:4326",
    )
    gridfinder = gpd.GeoDataFrame(
        {
            "geometry": [
                LineString([(57.5001, -20.2), (57.501, -20.2)]),
            ]
        },
        crs="EPSG:4326",
    )
    demand_points = gpd.GeoDataFrame(
        {"demand_mw": [3.0], "geometry": [Point(57.501, -20.2)]},
        crs="EPSG:4326",
    )
    graph = build_inferred_distribution_graph(
        substations,
        gridfinder_lines=gridfinder,
        max_anchor_distance_m=100,
    )
    graph = assign_proxy_demand_to_graph(graph, demand_points)

    supplied = topology_disconnection_impacts(graph)
    failed = topology_disconnection_impacts(graph, failed_bus_ids=["SUB_001"])

    assert supplied.empty
    assert failed["unserved_demand_mw"].sum() == 3.0


def test_proxy_demand_requires_distribution_nodes():
    substations = gpd.GeoDataFrame(
        {"bus_id": ["SUB_001"], "geometry": [Point(57.5, -20.2)]},
        crs="EPSG:4326",
    )
    demand_points = gpd.GeoDataFrame(
        {"demand_mw": [3.0], "geometry": [Point(57.501, -20.2)]},
        crs="EPSG:4326",
    )
    graph = build_inferred_distribution_graph(substations)

    with pytest.raises(ValueError, match="without distribution nodes"):
        assign_proxy_demand_to_graph(graph, demand_points)

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.base_topology import derive_base_topology


def test_base_topology_connects_short_route_gaps_and_keeps_substations():
    substations = gpd.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
            "name": ["A", "B"],
            "geometry": [Point(100, 0), Point(1_900, 0)],
        },
        crs="EPSG:32740",
    )
    routes = gpd.GeoDataFrame(
        {
            "route_id": ["R1", "R2"],
            "v_nom_kv": [66.0, None],
            "geometry": [
                LineString([(0, 0), (1_000, 0)]),
                LineString([(1_050, 0), (2_000, 0)]),
            ],
        },
        crs="EPSG:32740",
    )

    result = derive_base_topology(
        transmission_routes=routes,
        snapped_substations=substations,
    )

    assert result.substation_count == 2
    assert result.route_gap_count == 1
    assert result.route_gap_length_km == pytest.approx(0.05)
    assert result.connected_components == 1
    assert set(result.buses.query("kind == 'substation'")["bus_id"]) == {"A", "B"}
    assert result.lines["length_km"].sum() == pytest.approx(1.8)
    assert result.lines["s_nom_mva"].eq(10_000).all()
    assert result.lines["rating_basis"].eq("non_binding_topology_proxy").all()
    assert result.lines["source"].eq("derived_route_gap").any()

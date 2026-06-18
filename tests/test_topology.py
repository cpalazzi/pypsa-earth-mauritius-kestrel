import geopandas as gpd
from shapely.geometry import LineString, Point

from mu_star_energy.topology import build_substation_topology


def test_build_substation_topology_connects_consecutive_buses():
    substations = gpd.GeoDataFrame(
        {
            "bus_id": ["A", "B", "C"],
            "geometry": [Point(57.4, -20.2), Point(57.5, -20.2), Point(57.6, -20.2)],
        },
        crs="EPSG:4326",
    )
    routes = gpd.GeoDataFrame(
        {
            "voltage_kv_hint": [66],
            "geometry": [LineString([(57.39, -20.2), (57.61, -20.2)])],
        },
        crs="EPSG:4326",
    )

    result = build_substation_topology(substations, routes, snap_tolerance_m=500)

    assert len(result.lines) == 2
    assert set(result.lines[["bus0", "bus1"]].itertuples(index=False, name=None)) == {
        ("A", "B"),
        ("B", "C"),
    }


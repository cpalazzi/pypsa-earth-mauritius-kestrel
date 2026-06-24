import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.intake import validate_collaborator_inputs
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


def test_collaborator_input_check_lists_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        validate_collaborator_inputs(tmp_path)

    message = str(error.value)
    assert str(tmp_path) in message
    assert "power_demand/Power Demand.xlsx" in message
    assert "data/0-incoming/energy/collaborator" in message

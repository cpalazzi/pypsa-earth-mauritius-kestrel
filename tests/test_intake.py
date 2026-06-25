import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.intake import snap_substations_to_routes, validate_collaborator_inputs


def test_collaborator_input_check_lists_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        validate_collaborator_inputs(tmp_path)

    message = str(error.value)
    assert str(tmp_path) in message
    assert "power_demand/Power Demand.xlsx" in message
    assert "data/0-incoming/energy/collaborator" in message


def test_snap_substations_to_nearest_route_and_record_distance():
    substations = gpd.GeoDataFrame(
        {
            "bus_id": ["SUB_001", "SUB_002"],
            "name": ["A", "B"],
            "asset_type": ["substation", "substation"],
            "geometry": [Point(57.5, -20.2), Point(57.6, -20.21)],
        },
        crs="EPSG:4326",
    )
    routes = gpd.GeoDataFrame(
        {
            "route_id": ["ROUTE_001"],
            "geometry": [LineString([(57.4, -20.2), (57.7, -20.2)])],
        },
        crs="EPSG:4326",
    )

    snapped = snap_substations_to_routes(substations, routes)

    assert snapped["snapped_route_id"].eq("ROUTE_001").all()
    assert snapped["snapped_route_part_id"].eq("ROUTE_001_PART_001").all()
    assert snapped.loc[0, "snap_distance_m"] < 10
    assert snapped.loc[1, "snap_distance_m"] > 1_000
    assert snapped.loc[1, "geometry"].y == pytest.approx(-20.2, abs=1e-4)
    assert snapped.loc[1, "original_lat"] == pytest.approx(-20.21)

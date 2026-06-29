import pytest

from mu_star_energy.osm import ISLANDS, fetch_osm_roads, osm_roads_path


def test_island_registry_and_path():
    assert {"rodrigues", "agalega", "st_brandon"} <= set(ISLANDS)
    assert osm_roads_path("Rodrigues").name == "roads.parquet"
    assert osm_roads_path("Rodrigues").parent.name == "rodrigues"


def test_unknown_island_raises():
    with pytest.raises(ValueError, match="Unknown island"):
        fetch_osm_roads("atlantis")

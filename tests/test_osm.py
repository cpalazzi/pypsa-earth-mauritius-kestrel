import pytest

from mu_star_energy.osm import (
    OSMDownloadRequired,
    REGIONS,
    fetch_osm_power_features,
    fetch_osm_roads,
    osm_power_path,
    osm_roads_path,
    region_query,
    region_slug,
)


def test_region_shortcuts_and_paths():
    assert {"rodrigues", "agalega", "st_brandon"} <= set(REGIONS)
    assert region_query("mauritius") == "Mauritius Island, Mauritius"
    # Open-ended: any query is accepted, and slugged for cache/output paths.
    assert region_query("Rodrigues, Mauritius") == "Rodrigues, Mauritius"
    assert region_slug("Rodrigues, Mauritius") == "rodrigues_mauritius"
    assert osm_roads_path("Rodrigues").name == "roads.parquet"
    assert osm_roads_path("Rodrigues").parent.name == "rodrigues"
    assert osm_power_path("Rodrigues").name == "power.parquet"


def test_uncached_region_requires_download():
    with pytest.raises(OSMDownloadRequired):
        fetch_osm_roads("Nowhere Test Region 99999")
    with pytest.raises(OSMDownloadRequired):
        fetch_osm_power_features("Nowhere Test Region 99999")

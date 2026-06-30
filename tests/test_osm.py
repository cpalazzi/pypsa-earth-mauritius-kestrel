import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

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


def test_fetch_osm_power_features_handles_osmnx_multiindex(monkeypatch, tmp_path):
    ox = pytest.importorskip("osmnx")

    monkeypatch.setenv("MU_STAR_DATA_ROOT", str(tmp_path))
    index = pd.MultiIndex.from_tuples(
        [("way", 1001), ("node", 2002)],
        names=["element_type", "osmid"],
    )
    features = gpd.GeoDataFrame(
        {"power": ["substation", "generator"]},
        geometry=[Point(57.55, -20.25), Point(57.58, -20.29)],
        crs="EPSG:4326",
        index=index,
    )

    def fake_features_from_place(query, tags):
        assert query == "Mauritius Island, Mauritius"
        assert tags == {"power": ["substation", "plant", "generator"]}
        return features

    monkeypatch.setattr(ox, "features_from_place", fake_features_from_place)

    path = fetch_osm_power_features(
        "mauritius",
        overwrite=True,
        allow_download=True,
    )

    power = gpd.read_parquet(path)
    assert list(power["bus_id"]) == ["MAURITIUS_SUB_001", "MAURITIUS_SUB_002"]
    assert list(power["power"]) == ["substation", "generator"]
    assert power.crs == "EPSG:4326"

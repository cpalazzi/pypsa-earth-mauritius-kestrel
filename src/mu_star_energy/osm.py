"""Fetch OSM road networks for a region as inferred distribution-line geometry.

OSM roads are a proxy for where the low-voltage network runs; they are not
confirmed engineering data, so any network built from them stays labelled as
inferred. Fetching needs internet (the OSM Overpass API), so results are cached
under ``data/0-incoming/energy/osm/<region>/roads.parquet``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from mu_star_energy.paths import incoming_energy_dir

# Each key maps a region name to its OSM/Nominatim query; fetch one region at a
# time. For Mauritius the keys are "mauritius" (the main island only -- the bare
# country name "Mauritius" would also pull in the outer islands), "rodrigues",
# "agalega" and "st_brandon" (sparsely mapped, so an empty road network is
# expected). Add a key here to reuse this workflow for another area.
REGIONS: dict[str, str] = {
    "mauritius": "Mauritius Island, Mauritius",
    "rodrigues": "Rodrigues, Mauritius",
    "agalega": "Agalega, Mauritius",
    "st_brandon": "Saint Brandon, Mauritius",
}

GEOGRAPHIC_CRS = "EPSG:4326"


@dataclass(frozen=True)
class OSMRoadsOutput:
    region: str
    path: Path
    edge_count: int


def osm_roads_path(region: str) -> Path:
    return incoming_energy_dir() / "osm" / region.lower() / "roads.parquet"


def osm_power_path(region: str) -> Path:
    return incoming_energy_dir() / "osm" / region.lower() / "power.parquet"


def _empty_roads(region: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"source": [], "region": [], "geometry": []},
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    )


def _empty_power_features() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"source": [], "region": [], "bus_id": [], "power": [], "geometry": []},
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    )


def _validate_region(region: str) -> str:
    region = region.lower()
    if region not in REGIONS:
        raise ValueError(f"Unknown region {region!r}; choose from {sorted(REGIONS)}")
    return region


def fetch_osm_roads(
    region: str,
    *,
    network_type: str = "drive",
    overwrite: bool = False,
) -> OSMRoadsOutput:
    """Download the OSM road network for a region and cache it as LineStrings.

    Returns the cached file unless ``overwrite`` is set. Regions with no mapped
    roads (e.g. St Brandon) cache an empty layer rather than failing.
    """
    region = _validate_region(region)

    path = osm_roads_path(region)
    if path.exists() and not overwrite:
        return OSMRoadsOutput(region, path, len(gpd.read_parquet(path)))

    import osmnx as ox  # imported lazily; needs network access

    # Keep the Overpass response cache inside the (ignored) data tree.
    ox.settings.cache_folder = str(incoming_energy_dir() / "osm" / ".cache")

    try:
        from osmnx._errors import InsufficientResponseError
    except Exception:  # pragma: no cover - version-dependent import
        InsufficientResponseError = Exception  # type: ignore[assignment]

    try:
        graph = ox.graph_from_place(REGIONS[region], network_type=network_type)
        roads = ox.graph_to_gdfs(graph, nodes=False).reset_index()[["geometry"]]
        roads["source"] = "osm_roads"
        roads["region"] = region
        roads = roads[["source", "region", "geometry"]]
    except InsufficientResponseError:
        roads = _empty_roads(region)

    path.parent.mkdir(parents=True, exist_ok=True)
    roads.to_parquet(path)
    return OSMRoadsOutput(region, path, len(roads))


def fetch_osm_power_features(region: str, *, overwrite: bool = False) -> Path:
    """Download OSM power features for a region and cache them as bus points."""
    region = _validate_region(region)
    path = osm_power_path(region)
    if path.exists() and not overwrite:
        return path

    import osmnx as ox  # imported lazily; needs network access

    ox.settings.cache_folder = str(incoming_energy_dir() / "osm" / ".cache")

    try:
        from osmnx._errors import InsufficientResponseError
    except Exception:  # pragma: no cover - version-dependent import
        InsufficientResponseError = Exception  # type: ignore[assignment]

    try:
        features = ox.features_from_place(
            REGIONS[region],
            tags={"power": ["substation", "plant", "generator"]},
        )
        if features.empty:
            power = _empty_power_features()
        else:
            features = features[features.geometry.notna()].copy()
            if features.crs is None:
                features = features.set_crs(GEOGRAPHIC_CRS)
            metric = features.to_crs("EPSG:32740")
            power_values = (
                features["power"].astype(str).to_numpy()
                if "power" in features
                else [""] * len(metric)
            )
            power = gpd.GeoDataFrame(
                {
                    "source": "osm_power",
                    "region": region,
                    "bus_id": [
                        f"{region.upper()}_SUB_{number:03d}"
                        for number in range(1, len(metric) + 1)
                    ],
                    "power": power_values,
                },
                geometry=metric.geometry.centroid,
                crs="EPSG:32740",
            ).to_crs(GEOGRAPHIC_CRS)
    except InsufficientResponseError:
        power = _empty_power_features()

    path.parent.mkdir(parents=True, exist_ok=True)
    power.to_parquet(path)
    return path

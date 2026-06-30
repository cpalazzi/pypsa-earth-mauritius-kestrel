"""Fetch OSM road networks per island as inferred distribution-line geometry.

OSM roads are a proxy for where the low-voltage network runs; they are not
confirmed engineering data, so any network built from them stays labelled as
inferred. Fetching needs internet access (the OSM Overpass API), so results are
cached under ``data/0-incoming/energy/osm/<island>/roads.parquet``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from mu_star_energy.paths import incoming_energy_dir

# Mauritius and its outer islands. St Brandon is a near-empty fishing station,
# so an empty road network is expected and handled gracefully.
ISLANDS: dict[str, str] = {
    "mauritius": "Mauritius",
    "rodrigues": "Rodrigues, Mauritius",
    "agalega": "Agalega, Mauritius",
    "st_brandon": "Saint Brandon, Mauritius",
}

GEOGRAPHIC_CRS = "EPSG:4326"


@dataclass(frozen=True)
class OSMRoadsOutput:
    island: str
    path: Path
    edge_count: int


def osm_roads_path(island: str) -> Path:
    return incoming_energy_dir() / "osm" / island.lower() / "roads.parquet"


def osm_power_path(island: str) -> Path:
    return incoming_energy_dir() / "osm" / island.lower() / "power.parquet"


def _empty_roads(island: str) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"source": [], "island": [], "geometry": []},
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    )


def _empty_power_features() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"source": [], "island": [], "bus_id": [], "power": [], "geometry": []},
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    )


def _validate_island(island: str) -> str:
    island = island.lower()
    if island not in ISLANDS:
        raise ValueError(f"Unknown island {island!r}; choose from {sorted(ISLANDS)}")
    return island


def fetch_osm_roads(
    island: str,
    *,
    network_type: str = "drive",
    overwrite: bool = False,
) -> OSMRoadsOutput:
    """Download the OSM road network for an island and cache it as LineStrings.

    Returns the cached file unless ``overwrite`` is set. Islands with no mapped
    roads (e.g. St Brandon) cache an empty layer rather than failing.
    """
    island = _validate_island(island)

    path = osm_roads_path(island)
    if path.exists() and not overwrite:
        return OSMRoadsOutput(island, path, len(gpd.read_parquet(path)))

    import osmnx as ox  # imported lazily; needs network access

    # Keep the Overpass response cache inside the (ignored) data tree.
    ox.settings.cache_folder = str(incoming_energy_dir() / "osm" / ".cache")

    try:
        from osmnx._errors import InsufficientResponseError
    except Exception:  # pragma: no cover - version-dependent import
        InsufficientResponseError = Exception  # type: ignore[assignment]

    try:
        graph = ox.graph_from_place(ISLANDS[island], network_type=network_type)
        roads = ox.graph_to_gdfs(graph, nodes=False).reset_index()[["geometry"]]
        roads["source"] = "osm_roads"
        roads["island"] = island
        roads = roads[["source", "island", "geometry"]]
    except InsufficientResponseError:
        roads = _empty_roads(island)

    path.parent.mkdir(parents=True, exist_ok=True)
    roads.to_parquet(path)
    return OSMRoadsOutput(island, path, len(roads))


def fetch_osm_power_features(island: str, *, overwrite: bool = False) -> Path:
    """Download OSM power features for an island and cache them as bus points."""
    island = _validate_island(island)
    path = osm_power_path(island)
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
            ISLANDS[island],
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
                    "island": island,
                    "bus_id": [
                        f"{island.upper()}_SUB_{number:03d}"
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

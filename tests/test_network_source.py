import json

import geopandas as gpd
import pandas as pd
import pypsa
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.network_source import build_network
from mu_star_energy.osm import OSMDownloadRequired


def _write_base_inputs(input_dir):
    input_dir.mkdir(parents=True)
    buses = gpd.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
            "geometry": [Point(57.5, -20.2), Point(57.6, -20.2)],
        },
        crs="EPSG:4326",
    )
    buses.to_parquet(input_dir / "snapped_substations.parquet")
    pd.DataFrame(
        {
            "line_id": ["AB"],
            "bus0": ["A"],
            "bus1": ["B"],
            "v_nom_kv": [66],
            "length_km": [10.0],
            "s_nom_mva": [100.0],
        }
    ).to_csv(input_dir / "lines.csv", index=False)
    pd.DataFrame(
        {
            "generator_id": ["plant"],
            "bus_id": ["A"],
            "carrier": ["thermal"],
            "capacity_mw": [100.0],
            "capacity_basis": ["electrical_output"],
            "marginal_cost": [10.0],
        }
    ).to_csv(input_dir / "generators.csv", index=False)
    pd.DataFrame(
        {"bus_id": ["A", "B"], "service_weight": [0.0, 1.0]}
    ).to_csv(input_dir / "service_weights.csv", index=False)


def test_build_base_network_exports_network_files(tmp_path):
    input_dir = tmp_path / "processed" / "energy" / "provided"
    output_dir = tmp_path / "processed" / "energy" / "networks"
    _write_base_inputs(input_dir)

    outputs = build_network("base", input_dir=input_dir, output_dir=output_dir)

    metadata = json.loads(outputs.metadata.read_text())
    assert outputs.network.is_file()
    assert metadata["source"] == "base"
    assert metadata["buses"] == 2
    assert metadata["lines"] == 1
    assert metadata["generators"] == 1
    assert metadata["has_demand"] is False
    assert metadata["loads"] == 0
    assert metadata["inferred"] is False
    network = pypsa.Network(outputs.network)
    assert network.loads.empty


def test_build_base_network_requires_reviewed_inputs(tmp_path):
    with pytest.raises(FileNotFoundError, match="lines.csv"):
        build_network(
            "base",
            input_dir=tmp_path / "missing",
            output_dir=tmp_path / "networks",
        )


def test_build_inferred_without_region_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="requires a region"):
        build_network(
            "inferred",
            input_dir=tmp_path / "inputs",
            output_dir=tmp_path / "networks",
        )


def test_build_network_refuses_to_overwrite(tmp_path):
    input_dir = tmp_path / "processed" / "energy" / "provided"
    output_dir = tmp_path / "processed" / "energy" / "networks"
    _write_base_inputs(input_dir)
    build_network("base", input_dir=input_dir, output_dir=output_dir)
    with pytest.raises(FileExistsError, match="already exists"):
        build_network("base", input_dir=input_dir, output_dir=output_dir)
    outputs = build_network(
        "base", input_dir=input_dir, output_dir=output_dir, overwrite=True
    )
    assert outputs.network.is_file()


def test_build_inferred_network_for_region_uses_osm_fixtures(tmp_path, monkeypatch):
    roads = gpd.GeoDataFrame(
        {
            "source": ["osm_roads"],
            "region": ["rodrigues"],
            "geometry": [LineString([(63.42, -19.72), (63.421, -19.72)])],
        },
        crs="EPSG:4326",
    )
    power = gpd.GeoDataFrame(
        {
            "source": ["osm_power"],
            "region": ["rodrigues"],
            "bus_id": ["RODRIGUES_SUB_001"],
            "geometry": [Point(63.42, -19.72)],
        },
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_roads",
        lambda region, **kwargs: roads,
    )
    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_power_features",
        lambda region, **kwargs: power,
    )

    output_dir = tmp_path / "processed" / "energy" / "networks"
    outputs = build_network(
        "inferred",
        region="rodrigues",
        input_dir=tmp_path / "inputs",
        output_dir=output_dir,
        max_anchor_distance_m=100,
    )

    metadata = json.loads(outputs.metadata.read_text())
    network = pypsa.Network(outputs.network)

    assert outputs.network.name == "inferred-rodrigues.nc"
    assert outputs.metadata.name == "inferred-rodrigues_metadata.json"
    assert outputs.inferred_nodes.parent.name == "inferred_distribution-rodrigues"
    assert metadata["region"] == "rodrigues"
    assert metadata["road_edges"] == 1
    assert metadata["anchored_substations"] == 1
    assert metadata["provisional_root"] is False
    assert metadata["has_demand"] is False
    assert network.loads.empty
    assert len(network.lines) >= 1


def test_build_inferred_uses_gridfinder_and_cached_roads_without_power(
    tmp_path,
    monkeypatch,
):
    roads = gpd.GeoDataFrame(
        {
            "source": ["osm_roads"],
            "region": ["rodrigues"],
            "geometry": [LineString([(63.42, -19.72), (63.421, -19.72)])],
        },
        crs="EPSG:4326",
    )
    gridfinder = gpd.GeoDataFrame(
        {
            "source": ["gridfinder"],
            "region": ["rodrigues"],
            "geometry": [LineString([(63.422, -19.721), (63.423, -19.721)])],
        },
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_roads",
        lambda region, **kwargs: roads,
    )

    def missing_power(region, **kwargs):
        raise OSMDownloadRequired("power cache missing")

    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_power_features",
        missing_power,
    )

    outputs = build_network(
        "inferred",
        region="rodrigues",
        input_dir=tmp_path / "inputs",
        output_dir=tmp_path / "networks",
        gridfinder_lines=gridfinder,
        max_anchor_distance_m=1000,
    )

    metadata = json.loads(outputs.metadata.read_text())
    network = pypsa.Network(outputs.network)

    assert metadata["road_edges"] == 1
    assert metadata["gridfinder_edges"] == 1
    assert metadata["provisional_root"] is True
    assert any(
        str(line_id).startswith("gridfinder_") for line_id in network.lines.index
    )
    assert any(str(line_id).startswith("osm_") for line_id in network.lines.index)

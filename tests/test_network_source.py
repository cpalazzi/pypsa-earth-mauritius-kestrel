import json

import geopandas as gpd
import pandas as pd
import pypsa
import pytest
from shapely.geometry import LineString, Point

from mu_star_energy.network_source import build_network


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
    input_dir = tmp_path / "processed" / "energy" / "collaborator"
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


def test_build_inferred_network_exports_network_and_graph_tables(tmp_path):
    input_dir = tmp_path / "processed" / "energy" / "collaborator"
    output_dir = tmp_path / "processed" / "energy" / "networks"
    input_dir.mkdir(parents=True)
    gpd.GeoDataFrame(
        {"bus_id": ["SUB_001"], "geometry": [Point(57.5, -20.2)]},
        crs="EPSG:4326",
    ).to_parquet(input_dir / "snapped_substations.parquet")
    pd.DataFrame({"bus_id": ["SUB_001"], "service_weight": [1.0]}).to_csv(
        input_dir / "service_weights.csv",
        index=False,
    )
    line_path = tmp_path / "gridfinder.geojson"
    gpd.GeoDataFrame(
        {"geometry": [LineString([(57.5001, -20.2), (57.501, -20.2)])]},
        crs="EPSG:4326",
    ).to_file(line_path, driver="GeoJSON")

    outputs = build_network(
        "inferred",
        input_dir=input_dir,
        output_dir=output_dir,
        gridfinder_lines_path=line_path,
        osm_distribution_lines_path=None,
        allow_pypsa_earth_osm_fallback=False,
        max_anchor_distance_m=100,
    )

    metadata = json.loads(outputs.metadata.read_text())
    assert outputs.network.is_file()
    assert outputs.inferred_nodes.is_file()
    assert outputs.inferred_edges.is_file()
    assert metadata["source"] == "inferred"
    assert metadata["inferred"] is True
    assert metadata["has_demand"] is False
    assert metadata["loads"] == 0
    assert (outputs.inferred_nodes.parent / "service_weights.csv").is_file()


def test_build_inferred_network_for_island_uses_osm_fixtures(tmp_path, monkeypatch):
    roads = gpd.GeoDataFrame(
        {
            "source": ["osm_roads"],
            "island": ["rodrigues"],
            "geometry": [LineString([(63.42, -19.72), (63.421, -19.72)])],
        },
        crs="EPSG:4326",
    )
    power = gpd.GeoDataFrame(
        {
            "source": ["osm_power"],
            "island": ["rodrigues"],
            "bus_id": ["RODRIGUES_SUB_001"],
            "geometry": [Point(63.42, -19.72)],
        },
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_roads",
        lambda island: roads,
    )
    monkeypatch.setattr(
        "mu_star_energy.network_source.osm.fetch_osm_power_features",
        lambda island: power,
    )

    output_dir = tmp_path / "processed" / "energy" / "networks"
    outputs = build_network(
        "inferred",
        island="rodrigues",
        input_dir=tmp_path / "inputs",
        output_dir=output_dir,
        max_anchor_distance_m=100,
    )

    metadata = json.loads(outputs.metadata.read_text())
    network = pypsa.Network(outputs.network)

    assert outputs.network.name == "inferred-rodrigues.nc"
    assert outputs.metadata.name == "inferred-rodrigues_metadata.json"
    assert outputs.inferred_nodes.parent.name == "inferred_distribution-rodrigues"
    assert metadata["island"] == "rodrigues"
    assert metadata["road_edges"] == 1
    assert metadata["anchored_substations"] == 1
    assert metadata["provisional_root"] is False
    assert metadata["has_demand"] is False
    assert network.loads.empty
    assert len(network.lines) >= 1

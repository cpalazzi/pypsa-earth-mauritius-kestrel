import pandas as pd
import pypsa
import pytest

from mu_star_energy.model import EnergyModel, apply_disruptions
from mu_star_energy.network import assert_fixed_capacity, build_operational_network


def simple_network():
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2025-01-01", periods=2, freq="h"))
    network.add("Bus", "A", v_nom=66)
    network.add("Bus", "B", v_nom=66)
    network.add(
        "Line",
        "AB",
        bus0="A",
        bus1="B",
        s_nom=100,
        s_nom_extendable=False,
        x=0.1,
        r=0.0,
    )
    network.add(
        "Generator",
        "plant",
        bus="A",
        p_nom=50,
        p_nom_extendable=False,
        p_max_pu=1.0,
    )
    network.add("Carrier", "load_shedding")
    network.add(
        "Generator",
        "load_shedding::B",
        bus="B",
        carrier="load_shedding",
        p_nom=100,
        p_nom_extendable=False,
        marginal_cost=10_000,
    )
    network.add("Load", "load::B", bus="B", p_set=40)
    return network


def test_generator_disruption_changes_availability_without_expansion():
    network = simple_network()
    disrupted = apply_disruptions(
        network,
        [{"component": "Generator", "asset_id": "plant", "available_fraction": 0.25}],
    )

    assert disrupted.generators.at["plant", "p_max_pu"] == 0.25
    assert network.generators.at["plant", "p_max_pu"] == 1.0
    assert_fixed_capacity(disrupted)


def test_bus_disruption_disconnects_lines_and_physical_generation():
    disrupted = apply_disruptions(
        simple_network(),
        [{"component": "Bus", "asset_id": "A", "available_fraction": 0.0}],
    )

    assert disrupted.lines.at["AB", "s_max_pu"] == 0.0
    assert disrupted.generators.at["plant", "p_max_pu"] == 0.0


def test_simulate_reports_unserved_energy_after_generator_derating():
    result = EnergyModel(solver_name="highs").simulate(
        simple_network(),
        [{"component": "Generator", "asset_id": "plant", "available_fraction": 0.25}],
    )

    assert result.metrics["unserved_energy_mwh"] == 55.0
    assert result.metrics["served_fraction"] == 0.3125


def test_operational_network_rejects_missing_generator_marginal_cost():
    geopandas = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")

    buses = geopandas.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
            "v_nom_kv": [66, 66],
            "geometry": [
                shapely_geometry.Point(57.5, -20.2),
                shapely_geometry.Point(57.6, -20.2),
            ],
        },
        crs="EPSG:4326",
    )
    lines = geopandas.GeoDataFrame(
        {
            "line_id": ["AB"],
            "bus0": ["A"],
            "bus1": ["B"],
            "v_nom_kv": [66],
            "length_km": [10.0],
            "s_nom_mva": [100.0],
            "geometry": [
                shapely_geometry.LineString([(57.5, -20.2), (57.6, -20.2)])
            ],
        },
        crs="EPSG:4326",
    )
    generators = pd.DataFrame(
        {
            "generator_id": ["plant"],
            "bus_id": ["A"],
            "carrier": ["thermal"],
            "capacity_mw": [50.0],
            "marginal_cost": [float("nan")],
        }
    )
    demand = pd.DataFrame(
        {"demand_mw": [40.0]},
        index=pd.date_range("2025-01-01", periods=1, freq="h"),
    )
    service_weights = pd.DataFrame(
        {"bus_id": ["A", "B"], "service_weight": [0.5, 0.5]}
    )

    with pytest.raises(ValueError, match="marginal costs are incomplete"):
        build_operational_network(
            buses, lines, generators, demand, service_weights
        )

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


def test_simulate_result_keeps_mu_star_metrics_shape():
    result = EnergyModel(solver_name="highs").simulate(simple_network(), [])

    expected_keys = {
        "status",
        "condition",
        "total_demand_mwh",
        "unserved_energy_mwh",
        "served_energy_mwh",
        "served_fraction",
        "objective",
    }
    assert expected_keys <= set(result.metrics)
    assert isinstance(result.metrics, dict)
    assert result.network is not None


def test_operational_network_rejects_missing_generator_marginal_cost():
    geopandas = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")

    buses = geopandas.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
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

    with pytest.raises(ValueError, match="running costs are incomplete"):
        build_operational_network(
            buses, lines, generators, demand, service_weights
        )


def test_operational_network_uses_profile_values_and_time_step_duration():
    geopandas = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")

    buses = geopandas.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
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
            "capacity_mw": [100.0],
            "capacity_basis": ["electrical_output"],
            "marginal_cost": [50.0],
            "efficiency": [0.4],
        }
    )
    demand = pd.DataFrame(
        {"demand_mw": [40.0, 60.0]},
        index=pd.date_range("2025-01-01", periods=2, freq="30min"),
    )
    service_weights = pd.DataFrame(
        {"bus_id": ["A", "B"], "service_weight": [0.25, 0.75]}
    )

    network = build_operational_network(
        buses, lines, generators, demand, service_weights
    )

    assert network.snapshot_weightings.generators.eq(0.5).all()
    assert network.generators.at["plant", "p_nom"] == 100.0
    assert network.generators.at["plant", "efficiency"] == 0.4
    assert network.lines.at["AB", "s_nom"] == 100.0
    assert network.buses.loc[["A", "B"], "v_nom"].eq(66.0).all()
    assert network.loads_t.p_set["load::A"].tolist() == [10.0, 15.0]
    assert network.loads_t.p_set["load::B"].tolist() == [30.0, 45.0]

    result = EnergyModel(solver_name="highs").simulate(network, [])
    assert result.metrics["total_demand_mwh"] == 50.0
    assert result.metrics["unserved_energy_mwh"] == 0.0


def test_operational_network_applies_generator_availability_profile():
    geopandas = pytest.importorskip("geopandas")
    shapely_geometry = pytest.importorskip("shapely.geometry")

    buses = geopandas.GeoDataFrame(
        {
            "bus_id": ["A"],
            "geometry": [shapely_geometry.Point(57.5, -20.2)],
        },
        crs="EPSG:4326",
    )
    lines = geopandas.GeoDataFrame(
        {
            "line_id": pd.Series(dtype="object"),
            "bus0": pd.Series(dtype="object"),
            "bus1": pd.Series(dtype="object"),
            "v_nom_kv": pd.Series(dtype="float64"),
            "length_km": pd.Series(dtype="float64"),
            "s_nom_mva": pd.Series(dtype="float64"),
        }
    )
    generators = pd.DataFrame(
        {
            "generator_id": ["plant"],
            "bus_id": ["A"],
            "carrier": ["thermal"],
            "capacity_mw": [100.0],
            "capacity_basis": ["electrical_output"],
            "marginal_cost": [50.0],
        }
    )
    demand = pd.DataFrame(
        {"demand_mw": [80.0, 80.0]},
        index=pd.date_range("2025-01-01", periods=2, freq="h"),
    )
    service_weights = pd.DataFrame({"bus_id": ["A"], "service_weight": [1.0]})
    availability = pd.DataFrame({"plant": [0.5, 1.0]}, index=demand.index)

    network = build_operational_network(
        buses,
        lines,
        generators,
        demand,
        service_weights,
        generator_availability=availability,
    )
    result = EnergyModel(solver_name="highs").simulate(network, [])

    assert network.generators_t.p_max_pu["plant"].tolist() == [0.5, 1.0]
    assert result.metrics["unserved_energy_mwh"] == 30.0


def test_operational_network_rejects_irregular_profile_times():
    demand = pd.DataFrame(
        {"demand_mw": [40.0, 45.0, 50.0]},
        index=pd.DatetimeIndex(
            ["2025-01-01 00:00", "2025-01-01 01:00", "2025-01-01 03:00"]
        ),
    )

    with pytest.raises(ValueError, match="regular time-step length"):
        from mu_star_energy.network import _time_step_hours

        _time_step_hours(demand.index)

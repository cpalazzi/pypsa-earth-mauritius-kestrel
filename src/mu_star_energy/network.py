"""Build a PyPSA model of the existing electricity system."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pypsa


def _require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns: {sorted(missing)}")


def _time_step_hours(index: pd.Index) -> float:
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("Demand profile index must contain dates and times")
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError("Demand profile dates and times must be unique and ordered")
    if len(index) < 2:
        return 1.0

    intervals = index.to_series().diff().dropna().dt.total_seconds() / 3600
    if (intervals <= 0).any() or not np.allclose(intervals, intervals.iloc[0]):
        raise ValueError("Demand profile must use one regular time-step length")
    return float(intervals.iloc[0])


def _bus_voltage_kv(
    bus_id: str,
    bus_row: pd.Series,
    lines: pd.DataFrame,
) -> float:
    """Return one nominal bus voltage consistent with its connected AC lines."""
    connected = lines.loc[
        lines["bus0"].astype(str).eq(bus_id) | lines["bus1"].astype(str).eq(bus_id),
        "v_nom_kv",
    ].dropna()
    connected_voltages = np.unique(connected.astype(float))

    explicit_voltage = bus_row.get("v_nom_kv")
    if pd.notna(explicit_voltage):
        explicit_voltage = float(explicit_voltage)
        if connected_voltages.size and not np.allclose(
            connected_voltages,
            explicit_voltage,
        ):
            raise ValueError(
                f"Bus {bus_id} voltage does not match its connected line voltages"
            )
        return explicit_voltage
    if connected_voltages.size == 1:
        return float(connected_voltages[0])
    if connected_voltages.size > 1:
        raise ValueError(
            f"Bus {bus_id} has multiple line voltages. Represent each voltage "
            "level as a separate bus connected by a Transformer."
        )
    return 66.0


def build_operational_network(
    buses: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    generators: pd.DataFrame,
    demand_profile: pd.DataFrame,
    service_weights: pd.DataFrame,
    *,
    generator_availability: pd.DataFrame | None = None,
    value_of_lost_load: float = 10_000,
    line_reactance_ohm_per_km: float = 0.4,
) -> pypsa.Network:
    """Build a time-series supply model using only existing assets.

    The model cannot build extra capacity. Missing line limits or power-station
    capacities cause a clear error rather than being estimated by the model.

    Generator ``capacity_mw`` is electrical output capacity and is passed
    directly to ``Generator.p_nom``. Optional generator availability values
    must be fractions between zero and one, indexed by the same timestamps as
    ``demand_profile`` and with one column per physical generator. Line
    ``s_nom_mva`` is an apparent-power rating. This function does not convert
    capacities to or from an LHV basis.
    """
    _require_columns(buses, {"bus_id", "geometry"}, "buses")
    _require_columns(
        lines,
        {
            "line_id",
            "bus0",
            "bus1",
            "v_nom_kv",
            "length_km",
            "s_nom_mva",
        },
        "lines",
    )
    _require_columns(
        generators,
        {"generator_id", "bus_id", "carrier", "capacity_mw", "marginal_cost"},
        "generators",
    )
    _require_columns(service_weights, {"bus_id", "service_weight"}, "service_weights")

    if lines["s_nom_mva"].isna().any():
        raise ValueError(
            "Maximum line power is incomplete; populate s_nom_mva before simulation"
        )
    if generators["capacity_mw"].isna().any():
        raise ValueError(
            "Power-station maximum output is incomplete; populate capacity_mw "
            "before simulation"
        )
    if "capacity_basis" in generators:
        invalid_basis = ~generators["capacity_basis"].astype(str).str.lower().eq(
            "electrical_output"
        )
        if invalid_basis.any():
            raise ValueError(
                "Generator capacity_basis must be 'electrical_output'; "
                "Generator.p_nom is output-side MW"
            )
    if generators["marginal_cost"].isna().any():
        raise ValueError(
            "Power-station running costs are incomplete; populate marginal_cost "
            "before simulation"
        )
    if generators["bus_id"].isna().any():
        raise ValueError("Power-station substation assignments are incomplete")
    if demand_profile.empty:
        raise ValueError("Demand profile is empty")
    demand_profile = demand_profile.apply(pd.to_numeric, errors="coerce")
    if demand_profile.isna().any().any():
        raise ValueError("Demand profile contains missing values")
    if (demand_profile < 0).any().any():
        raise ValueError("Demand profile cannot contain negative demand")
    if generator_availability is not None:
        if not generator_availability.index.equals(demand_profile.index):
            raise ValueError(
                "Generator availability must use the same timestamps as demand_profile"
            )
        generator_availability = generator_availability.apply(
            pd.to_numeric,
            errors="coerce",
        )
        if generator_availability.isna().any().any():
            raise ValueError("Generator availability contains missing values")
        if (
            (generator_availability < 0).any().any()
            or (generator_availability > 1).any().any()
        ):
            raise ValueError("Generator availability values must lie between zero and one")

    network = pypsa.Network()
    time_step_hours = _time_step_hours(demand_profile.index)
    network.set_snapshots(demand_profile.index)
    network.snapshot_weightings.loc[:, :] = time_step_hours

    bus_frame = buses.to_crs("EPSG:4326").set_index("bus_id")
    for bus_id, row in bus_frame.iterrows():
        bus_id = str(bus_id)
        network.add(
            "Bus",
            bus_id,
            x=float(row.geometry.x),
            y=float(row.geometry.y),
            v_nom=_bus_voltage_kv(bus_id, row, lines),
            carrier="AC",
        )

    for _, row in lines.iterrows():
        # PyPSA Line.s_nom is the branch apparent-power rating in MVA.
        network.add(
            "Line",
            str(row["line_id"]),
            bus0=str(row["bus0"]),
            bus1=str(row["bus1"]),
            length=float(row["length_km"]),
            s_nom=float(row["s_nom_mva"]),
            s_nom_extendable=False,
            r=0.0,
            x=max(float(row["length_km"]) * line_reactance_ohm_per_km, 1e-6),
        )

    for _, row in generators.iterrows():
        carrier = str(row["carrier"])
        if carrier not in network.carriers.index:
            network.add("Carrier", carrier)
        # Generator.p_nom limits electrical output at the connected bus.
        network.add(
            "Generator",
            str(row["generator_id"]),
            bus=str(row["bus_id"]),
            carrier=carrier,
            p_nom=float(row["capacity_mw"]),
            p_nom_extendable=False,
            marginal_cost=float(row["marginal_cost"]),
            efficiency=float(row.get("efficiency", 1.0)),
        )

    physical_generator_ids = generators["generator_id"].astype(str).tolist()
    if generator_availability is not None:
        availability = generator_availability.reindex(columns=physical_generator_ids)
        if availability.isna().any().any():
            missing = sorted(set(physical_generator_ids) - set(generator_availability.columns))
            raise ValueError(
                "Generator availability must contain one complete column per "
                f"generator_id; missing: {missing}"
            )
        network.generators_t.p_max_pu.loc[:, physical_generator_ids] = availability

    weights = service_weights.set_index("bus_id")["service_weight"].reindex(
        bus_frame.index
    )
    if weights.isna().any() or not np.isclose(weights.sum(), 1.0):
        raise ValueError(
            "Demand shares must cover every substation (bus_id) and add to one"
        )

    if "demand_mw" in demand_profile.columns:
        total_demand = demand_profile["demand_mw"]
        demand_by_bus = pd.DataFrame(
            {bus_id: total_demand * weight for bus_id, weight in weights.items()}
        )
    else:
        demand_by_bus = demand_profile.reindex(columns=bus_frame.index)
        if demand_by_bus.isna().any().any():
            raise ValueError(
                "Demand profile must contain demand_mw or one complete column "
                "per substation (bus_id)"
            )

    if "load_shedding" not in network.carriers.index:
        network.add("Carrier", "load_shedding")
    for bus_id in bus_frame.index:
        load_id = f"load::{bus_id}"
        shed_id = f"load_shedding::{bus_id}"
        network.add("Load", load_id, bus=bus_id)
        network.loads_t.p_set[load_id] = demand_by_bus[bus_id]
        network.add(
            "Generator",
            shed_id,
            bus=bus_id,
            carrier="load_shedding",
            p_nom=max(float(demand_by_bus[bus_id].max()), 1.0),
            p_nom_extendable=False,
            marginal_cost=float(value_of_lost_load),
        )

    assert_fixed_capacity(network)
    return network


def assert_fixed_capacity(network: pypsa.Network) -> None:
    """Reject settings that let the model build extra assets."""
    checks = (
        ("generators", "p_nom_extendable"),
        ("lines", "s_nom_extendable"),
        ("links", "p_nom_extendable"),
        ("storage_units", "p_nom_extendable"),
        ("stores", "e_nom_extendable"),
    )
    for component, column in checks:
        frame = getattr(network, component)
        if column in frame and frame[column].fillna(False).any():
            raise ValueError(f"{component}.{column} must be false for interruption modelling")

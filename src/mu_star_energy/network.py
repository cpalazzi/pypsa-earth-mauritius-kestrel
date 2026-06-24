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


def build_operational_network(
    buses: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    generators: pd.DataFrame,
    demand_profile: pd.DataFrame,
    service_weights: pd.DataFrame,
    *,
    value_of_lost_load: float = 10_000,
    line_reactance_ohm_per_km: float = 0.4,
) -> pypsa.Network:
    """Build an hourly supply model using only existing assets.

    The model cannot build extra capacity. Missing line limits or power-station
    capacities cause a clear error rather than being estimated by the model.
    """
    _require_columns(buses, {"bus_id", "geometry"}, "buses")
    _require_columns(
        lines,
        {"line_id", "bus0", "bus1", "v_nom_kv", "length_km", "s_nom_mva"},
        "lines",
    )
    _require_columns(
        generators,
        {"generator_id", "bus_id", "carrier", "capacity_mw", "marginal_cost"},
        "generators",
    )
    _require_columns(service_weights, {"bus_id", "service_weight"}, "service_weights")

    if lines["s_nom_mva"].isna().any():
        raise ValueError("Line ratings are incomplete; populate s_nom_mva before simulation")
    if generators["capacity_mw"].isna().any():
        raise ValueError(
            "Generator capacities are incomplete; populate capacity_mw before simulation"
        )
    if generators["marginal_cost"].isna().any():
        raise ValueError(
            "Power-station running costs are incomplete; populate marginal_cost "
            "before simulation"
        )
    if generators["bus_id"].isna().any():
        raise ValueError("Generator-to-substation assignments are incomplete")

    network = pypsa.Network()
    network.set_snapshots(pd.DatetimeIndex(demand_profile.index))

    bus_frame = buses.to_crs("EPSG:4326").set_index("bus_id")
    for bus_id, row in bus_frame.iterrows():
        network.add(
            "Bus",
            str(bus_id),
            x=float(row.geometry.x),
            y=float(row.geometry.y),
            v_nom=float(row.get("v_nom_kv", 66)),
            carrier="AC",
        )

    for _, row in lines.iterrows():
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
    """Reject accidental capacity-expansion settings."""
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

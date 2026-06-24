"""Calculate electricity supply when existing assets are unavailable."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pypsa

from mu_star_energy.network import assert_fixed_capacity


@dataclass(frozen=True)
class SimulationResult:
    metrics: dict[str, float | str]
    network: pypsa.Network


def apply_disruptions(
    network: pypsa.Network, disruptions: pd.DataFrame | list[dict[str, object]]
) -> pypsa.Network:
    """Copy the network and reduce the usable share of selected assets."""
    disrupted = network.copy()
    frame = pd.DataFrame(disruptions)
    if frame.empty:
        return disrupted
    required = {"component", "asset_id", "available_fraction"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Disruptions missing columns: {sorted(missing)}")

    for _, event in frame.iterrows():
        component = str(event["component"]).lower()
        asset_id = str(event["asset_id"])
        fraction = float(event["available_fraction"])
        if not 0 <= fraction <= 1:
            raise ValueError("available_fraction must lie between zero and one")

        if component == "generator":
            if asset_id not in disrupted.generators.index:
                raise KeyError(f"Unknown generator {asset_id}")
            disrupted.generators.at[asset_id, "p_max_pu"] *= fraction
        elif component == "line":
            if asset_id not in disrupted.lines.index:
                raise KeyError(f"Unknown line {asset_id}")
            disrupted.lines.at[asset_id, "s_max_pu"] *= fraction
        elif component == "bus":
            if asset_id not in disrupted.buses.index:
                raise KeyError(f"Unknown bus {asset_id}")
            incident = (disrupted.lines.bus0 == asset_id) | (
                disrupted.lines.bus1 == asset_id
            )
            disrupted.lines.loc[incident, "s_max_pu"] = 0.0
            connected_generators = disrupted.generators.bus.eq(asset_id)
            physical = connected_generators & ~disrupted.generators.carrier.eq(
                "load_shedding"
            )
            disrupted.generators.loc[physical, "p_max_pu"] = 0.0
        else:
            raise ValueError(f"Unsupported disruption component {event['component']!r}")
    return disrupted


class EnergyModel:
    """Calculate electricity supply using only the existing assets."""

    def __init__(self, solver_name: str = "highs") -> None:
        self.solver_name = solver_name

    def simulate(
        self,
        network: pypsa.Network,
        disruptions: pd.DataFrame | list[dict[str, object]],
    ) -> SimulationResult:
        assert_fixed_capacity(network)
        disrupted = apply_disruptions(network, disruptions)
        status, condition = disrupted.optimize(solver_name=self.solver_name)
        if status != "ok":
            raise RuntimeError(
                "Electricity supply calculation failed: "
                f"status={status}, condition={condition}"
            )

        weights = disrupted.snapshot_weightings.generators.reindex(
            disrupted.snapshots
        ).fillna(1.0)
        demand = disrupted.get_switchable_as_dense("Load", "p_set").reindex(
            disrupted.snapshots
        )
        total_demand = float(demand.mul(weights, axis=0).sum().sum())
        shedding_names = disrupted.generators.index[
            disrupted.generators.carrier.eq("load_shedding")
        ]
        shedding = disrupted.generators_t.p.reindex(columns=shedding_names).clip(
            lower=0.0
        )
        unserved = float(shedding.mul(weights, axis=0).sum().sum())
        return SimulationResult(
            metrics={
                "status": status,
                "condition": condition,
                "total_demand_mwh": total_demand,
                "unserved_energy_mwh": unserved,
                "served_energy_mwh": total_demand - unserved,
                "served_fraction": (total_demand - unserved) / total_demand
                if total_demand
                else 1.0,
                "objective": float(disrupted.objective),
            },
            network=disrupted,
        )

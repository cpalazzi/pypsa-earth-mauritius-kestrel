"""Load a saved PyPSA network, run baseline/outage cases and write results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pypsa

from mu_star_energy.damage import damage_to_disruptions
from mu_star_energy.model import EnergyModel, SimulationResult
from mu_star_energy.network import attach_demand


@dataclass(frozen=True)
class RunOutputs:
    demand_summary: Path
    summary_metrics: Path
    baseline_metrics: Path
    baseline_unserved: Path
    baseline_network: Path | None
    outage_metrics: Path | None = None
    outage_unserved: Path | None = None
    outage_network: Path | None = None


def read_time_series_csv(path: Path, *, label: str) -> pd.DataFrame:
    """Read a timestamp-indexed CSV and coerce all value columns to numbers."""
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{label} is empty")
    timestamp_column = frame.columns[0]
    timestamps = pd.to_datetime(frame.pop(timestamp_column), errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"{label} timestamp column contains unreadable values")
    frame.index = pd.DatetimeIndex(timestamps, name="timestamp")
    if frame.empty:
        raise ValueError(f"{label} must contain at least one value column")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.isna().any().any():
        raise ValueError(f"{label} contains missing or non-numeric values")
    return frame


def _load_disruptions(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame(columns=["component", "asset_id", "available_fraction"])
    frame = pd.read_csv(path)
    if "available_fraction" in frame.columns:
        return frame
    if "damage_fraction" in frame.columns:
        return damage_to_disruptions(frame)
    if "fraction" in frame.columns:
        damage = frame.rename(columns={"fraction": "damage_fraction"})
        return damage_to_disruptions(damage)
    raise ValueError("Disruption file must contain available_fraction, damage_fraction or fraction")


def _metrics_frame(rows: list[tuple[str, SimulationResult]]) -> pd.DataFrame:
    return pd.DataFrame([{"case": case, **result.metrics} for case, result in rows]).set_index(
        "case"
    )


def _summarize_demand_series(
    *,
    scope: str,
    demand_mw: pd.Series,
    weights: pd.Series,
    duration_hours: float,
) -> dict[str, float | int | str]:
    energy_mwh = float(demand_mw.mul(weights, axis=0).sum())
    peak_mw = float(demand_mw.max()) if not demand_mw.empty else 0.0
    average_mw = energy_mwh / duration_hours if duration_hours else 0.0
    return {
        "scope": scope,
        "snapshot_count": int(demand_mw.size),
        "duration_hours": duration_hours,
        "profile_demand_mwh": energy_mwh,
        "annualized_demand_mwh": average_mw * 8760,
        "peak_demand_mw": peak_mw,
        "average_demand_mw": average_mw,
        "load_factor": average_mw / peak_mw if peak_mw else 0.0,
    }


def _demand_summary_frame(network) -> pd.DataFrame:
    demand = network.get_switchable_as_dense("Load", "p_set").reindex(network.snapshots)
    weights = network.snapshot_weightings.generators.reindex(network.snapshots).fillna(1.0)
    duration_hours = float(weights.sum())

    load_to_bus = network.loads["bus"].reindex(demand.columns)
    demand_by_bus = demand.rename(columns=load_to_bus.to_dict())
    demand_by_bus = demand_by_bus.T.groupby(level=0).sum().T

    rows = [
        _summarize_demand_series(
            scope="system",
            demand_mw=demand_by_bus.sum(axis=1),
            weights=weights,
            duration_hours=duration_hours,
        )
    ]
    rows.extend(
        _summarize_demand_series(
            scope=f"bus::{bus_id}",
            demand_mw=demand_by_bus[bus_id],
            weights=weights,
            duration_hours=duration_hours,
        )
        for bus_id in sorted(demand_by_bus.columns.astype(str))
    )
    return pd.DataFrame(rows).set_index("scope")


def _write_demand_summary(path: Path, network) -> None:
    _demand_summary_frame(network).to_csv(path)


def _write_metrics(path: Path, result: SimulationResult) -> None:
    path.write_text(json.dumps(result.metrics, indent=2, sort_keys=True), encoding="utf-8")


def _write_unserved_energy(path: Path, result: SimulationResult) -> None:
    shedding_names = result.network.generators.index[
        result.network.generators.carrier.eq("load_shedding")
    ]
    shedding = result.network.generators_t.p.reindex(columns=shedding_names).clip(lower=0.0)
    weights = result.network.snapshot_weightings.generators.reindex(
        result.network.snapshots
    ).fillna(1.0)
    unserved = shedding.mul(weights, axis=0)
    unserved = unserved.rename(
        columns={name: name.replace("load_shedding::", "") for name in shedding_names}
    )
    unserved.index.name = "timestamp"
    unserved.to_csv(path)


def _export_network(path: Path, result: SimulationResult, *, export_networks: bool) -> Path | None:
    if not export_networks:
        return None
    result.network.export_to_netcdf(path)
    return path


def run_interruption_analysis(
    input_dir: Path,
    output_dir: Path,
    *,
    network_path: Path,
    solver_name: str = "highs",
    value_of_lost_load: float = 10_000,
    disruptions_path: Path | None = None,
    generator_availability_path: Path | None = None,
    require_no_baseline_shedding: bool = False,
    export_networks: bool = True,
) -> RunOutputs:
    """Load a saved fixed-capacity network and run optional outage cases."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    network_path = Path(network_path)
    if not network_path.exists():
        raise FileNotFoundError(f"Saved PyPSA network is missing: {network_path}")
    demand_path = input_dir / "demand_profile.csv"
    if not demand_path.exists():
        raise FileNotFoundError(
            f"{demand_path} is missing. Saved networks are topology-only; "
            "attach demand from demand_profile.csv before simulation."
        )
    demand = read_time_series_csv(demand_path, label="demand_profile")
    service_weights = pd.read_csv(input_dir / "service_weights.csv")
    generator_availability = (
        read_time_series_csv(
            generator_availability_path,
            label="generator_availability",
        )
        if generator_availability_path
        else None
    )
    network = attach_demand(
        pypsa.Network(network_path),
        demand,
        service_weights,
        generator_availability=generator_availability,
        value_of_lost_load=value_of_lost_load,
    )
    demand_summary = output_dir / "demand_summary.csv"
    _write_demand_summary(demand_summary, network)

    model = EnergyModel(solver_name=solver_name)

    baseline = model.simulate(network, [])
    if require_no_baseline_shedding and baseline.metrics["unserved_energy_mwh"] > 1e-6:
        raise RuntimeError(
            "Baseline run has unserved demand; review capacities, demand and topology"
        )

    baseline_metrics = output_dir / "baseline_metrics.json"
    baseline_unserved = output_dir / "baseline_unserved_energy_mwh_by_substation.csv"
    baseline_network = _export_network(
        output_dir / "baseline_network.nc",
        baseline,
        export_networks=export_networks,
    )
    _write_metrics(baseline_metrics, baseline)
    _write_unserved_energy(baseline_unserved, baseline)

    rows = [("baseline", baseline)]
    outage_metrics = None
    outage_unserved = None
    outage_network = None
    disruptions = _load_disruptions(disruptions_path)
    if not disruptions.empty:
        outage = model.simulate(network, disruptions)
        outage_metrics = output_dir / "outage_metrics.json"
        outage_unserved = output_dir / "outage_unserved_energy_mwh_by_substation.csv"
        outage_network = _export_network(
            output_dir / "outage_network.nc",
            outage,
            export_networks=export_networks,
        )
        _write_metrics(outage_metrics, outage)
        _write_unserved_energy(outage_unserved, outage)
        rows.append(("outage", outage))

    summary_metrics = output_dir / "summary_metrics.csv"
    _metrics_frame(rows).to_csv(summary_metrics)
    return RunOutputs(
        demand_summary=demand_summary,
        summary_metrics=summary_metrics,
        baseline_metrics=baseline_metrics,
        baseline_unserved=baseline_unserved,
        baseline_network=baseline_network,
        outage_metrics=outage_metrics,
        outage_unserved=outage_unserved,
        outage_network=outage_network,
    )

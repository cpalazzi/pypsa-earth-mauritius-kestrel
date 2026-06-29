import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from mu_star_energy.runner import read_time_series_csv, run_interruption_analysis


def _write_reviewed_inputs(input_dir):
    input_dir.mkdir(parents=True)
    buses = gpd.GeoDataFrame(
        {
            "bus_id": ["A", "B"],
            "name": ["A", "B"],
            "asset_type": ["substation", "substation"],
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
            "geometry": [LineString([(57.5, -20.2), (57.6, -20.2)]).wkt],
        }
    ).to_csv(input_dir / "existing_lines.csv", index=False)
    pd.DataFrame(
        {
            "generator_id": ["plant"],
            "bus_id": ["A"],
            "carrier": ["thermal"],
            "capacity_mw": [50.0],
            "capacity_basis": ["electrical_output"],
            "marginal_cost": [10.0],
        }
    ).to_csv(input_dir / "existing_generators.csv", index=False)
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=2, freq="h"),
            "demand_mw": [40.0, 40.0],
        }
    ).to_csv(input_dir / "demand_profile.csv", index=False)
    pd.DataFrame(
        {"bus_id": ["A", "B"], "service_weight": [0.0, 1.0]}
    ).to_csv(input_dir / "service_weights.csv", index=False)
    pd.DataFrame(
        {
            "component": ["Generator"],
            "asset_id": ["plant"],
            "available_fraction": [0.25],
        }
    ).to_csv(input_dir / "disruptions.csv", index=False)


def test_read_time_series_csv_uses_first_column_as_timestamp(tmp_path):
    path = tmp_path / "profile.csv"
    pd.DataFrame(
        {
            "time": ["2025-01-01 00:00", "2025-01-01 01:00"],
            "demand_mw": ["1.5", "2.5"],
        }
    ).to_csv(path, index=False)

    result = read_time_series_csv(path, label="test_profile")

    assert result.index.name == "timestamp"
    assert result["demand_mw"].tolist() == [1.5, 2.5]


def test_run_interruption_analysis_writes_baseline_and_outage_outputs(tmp_path):
    input_dir = tmp_path / "processed" / "energy" / "collaborator"
    output_dir = tmp_path / "out" / "energy"
    _write_reviewed_inputs(input_dir)

    outputs = run_interruption_analysis(
        input_dir,
        output_dir,
        disruptions_path=input_dir / "disruptions.csv",
        export_networks=False,
    )

    summary = pd.read_csv(outputs.summary_metrics, index_col="case")
    outage_unserved = pd.read_csv(outputs.outage_unserved, index_col="timestamp")

    assert summary.loc["baseline", "unserved_energy_mwh"] == 0.0
    assert summary.loc["outage", "unserved_energy_mwh"] == 55.0
    assert outage_unserved["B"].sum() == 55.0
    assert outputs.baseline_metrics.is_file()
    assert outputs.outage_metrics.is_file()
    assert outputs.baseline_network is None
    assert outputs.outage_network is None

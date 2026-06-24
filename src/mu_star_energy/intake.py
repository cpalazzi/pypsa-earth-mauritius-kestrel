"""Convert collaborator source files into stable analysis-ready asset layers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
METRIC_CRS = "EPSG:32740"
GEOGRAPHIC_CRS = "EPSG:4326"
REQUIRED_COLLABORATOR_FILES = (
    "power_demand/Power Demand.xlsx",
    "substation/Substation.shp",
    "substation/Substation.shx",
    "substation/Substation.dbf",
    "substation/Substation.prj",
    "power_transmission/PowerGrid.shp",
    "power_transmission/PowerGrid.shx",
    "power_transmission/PowerGrid.dbf",
    "power_transmission/PowerGrid.prj",
    "generation_source/GenSource1.shp",
    "generation_source/GenSource1.shx",
    "generation_source/GenSource1.dbf",
    "generation_source/GenSource1.prj",
    "generation_source/GenSource2.shp",
    "generation_source/GenSource2.shx",
    "generation_source/GenSource2.dbf",
    "generation_source/GenSource2.prj",
)


@dataclass(frozen=True)
class PreparedAssets:
    substations: Path
    transmission_routes: Path
    generation_points: Path
    generation_areas: Path
    generation_register_template: Path
    monthly_peak_demand: Path
    annual_sector_demand: Path


def validate_collaborator_inputs(input_dir: Path) -> None:
    """Give a clear error when a received source file is missing."""
    input_dir = Path(input_dir)
    missing = [
        relative_path
        for relative_path in REQUIRED_COLLABORATOR_FILES
        if not (input_dir / relative_path).is_file()
    ]
    if not missing:
        return

    missing_list = "\n".join(f"  - {path}" for path in missing)
    message = (
        f"Collaborator input data are incomplete at:\n  {input_dir}\n\n"
        f"Missing files:\n{missing_list}\n\n"
        "Place the complete source folders under "
        "data/0-incoming/energy/collaborator, or set MU_STAR_DATA_ROOT to a "
        "data directory containing the same 0-incoming/energy/collaborator "
        "structure."
    )
    if "/data/incoming/" in input_dir.as_posix():
        message += (
            "\n\nThis path uses the previous unnumbered folder name. Restart "
            "the notebook kernel and run the first cell again."
        )
    raise FileNotFoundError(message)


def _read_gdf(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(GEOGRAPHIC_CRS)
    return gdf.to_crs(GEOGRAPHIC_CRS)


def _clean_label(value: object, fallback: str = "unnamed") -> str:
    if pd.isna(value):
        return fallback
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or fallback


def classify_generation(row: pd.Series) -> str:
    """Classify only explicit source labels; leave ambiguous assets unspecified."""
    text = " ".join(
        _clean_label(row.get(column), "")
        for column in ("Name", "PopupInfo", "FolderPath")
    ).lower()
    if "gamesa" in text or "wind" in text:
        return "wind"
    if "hydro" in text:
        return "hydro"
    if "solar" in text or "sarako" in text or "landscope" in text:
        return "solar"
    if "substation" in text or "sub-station" in text or "sub station" in text:
        return "substation"
    thermal_tokens = (
        "power station",
        "power plant",
        "ferney",
        "nicolay",
        "fort george",
        "saint louis",
    )
    if any(token in text for token in thermal_tokens):
        return "thermal"
    return "unspecified"


def _find_cell(frame: pd.DataFrame, pattern: str) -> tuple[int, int]:
    compiled = re.compile(pattern, flags=re.IGNORECASE)
    for row_i, row in frame.iterrows():
        for col_i, value in row.items():
            if isinstance(value, str) and compiled.search(value):
                return int(row_i), int(col_i)
    raise ValueError(f"Could not find workbook label matching {pattern!r}")


def extract_demand_workbook(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract monthly system peaks and annual customer-sector demand."""
    raw = pd.read_excel(path, sheet_name=0, header=None)

    year_row, year_col = _find_cell(raw, r"^\s*Year\s*$")
    header = raw.iloc[year_row]
    month_cols = [int(header[header.eq(month)].index[0]) for month in MONTHS]
    peak_rows: list[dict[str, object]] = []
    for row_i in range(year_row + 1, len(raw)):
        year = raw.iat[row_i, year_col]
        if pd.isna(year):
            if peak_rows:
                break
            continue
        if not isinstance(year, (int, float, np.integer, np.floating)):
            break
        values = [raw.iat[row_i, column] for column in month_cols]
        peak_rows.append({"year": int(year), **dict(zip(MONTHS, values, strict=True))})
    monthly_peak = (
        pd.DataFrame(peak_rows).set_index("year").apply(pd.to_numeric, errors="coerce")
    )

    unit_row, _ = _find_cell(raw, r"Unit\s*:\s*GWh")
    annual_year_row = unit_row + 1
    annual_year_cols = [
        int(column)
        for column, value in raw.iloc[annual_year_row].items()
        if pd.notna(value) and isinstance(value, (int, float, np.integer, np.floating))
    ]
    years = [int(raw.iat[annual_year_row, column]) for column in annual_year_cols]
    label_col = min(annual_year_cols) - 1
    annual_rows: list[dict[str, object]] = []
    for row_i in range(annual_year_row + 1, len(raw)):
        label = raw.iat[row_i, label_col]
        if pd.isna(label):
            continue
        label = _clean_label(str(label).replace("\n", " "))
        label = label.replace("Electricity demand - ", "").replace("Electricity demand ", "")
        for year, column in zip(years, annual_year_cols, strict=True):
            annual_rows.append(
                {"year": year, "category": label, "demand_gwh": raw.iat[row_i, column]}
            )
    annual = pd.DataFrame(annual_rows)
    annual["demand_gwh"] = pd.to_numeric(annual["demand_gwh"], errors="coerce")
    return monthly_peak, annual


def _station_points_from_areas(areas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    named = areas[areas["is_named"] & ~areas["category"].eq("substation")].copy()
    if named.empty:
        return gpd.GeoDataFrame(
            columns=["asset_id", "name", "asset_type", "geometry"], crs=GEOGRAPHIC_CRS
        )
    named["geometry"] = named.geometry.representative_point()
    return named.rename(columns={"label": "name", "category": "asset_type"})[
        ["asset_id", "name", "asset_type", "geometry"]
    ]


def prepare_collaborator_data(input_dir: Path, output_dir: Path) -> PreparedAssets:
    """Prepare source shapefiles and the CEB workbook for modelling."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    validate_collaborator_inputs(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    substations = _read_gdf(input_dir / "substation" / "Substation.shp").reset_index(drop=True)
    substations["bus_id"] = [f"SUB_{index + 1:03d}" for index in substations.index]
    substations["name"] = substations["bus_id"]
    substations["asset_type"] = "substation"

    routes = _read_gdf(input_dir / "power_transmission" / "PowerGrid.shp").reset_index(
        drop=True
    )
    routes["route_id"] = [f"ROUTE_{index + 1:03d}" for index in routes.index]
    routes["name"] = routes["Name"].combine_first(routes["FolderPath"]).apply(_clean_label)
    routes["voltage_kv_hint"] = (
        routes[["Name", "FolderPath"]]
        .fillna("")
        .agg(" ".join, axis=1)
        .str.extract(r"(\d+)\s*KV", expand=False)
        .astype(float)
    )
    routes["length_km"] = routes.to_crs(METRIC_CRS).length / 1000

    points = _read_gdf(input_dir / "generation_source" / "GenSource1.shp").reset_index(
        drop=True
    )
    points["asset_id"] = [f"GEN_POINT_{index + 1:03d}" for index in points.index]
    points["name"] = points["Name"].apply(_clean_label)
    points["asset_type"] = points.apply(classify_generation, axis=1)

    areas = _read_gdf(input_dir / "generation_source" / "GenSource2.shp").reset_index(
        drop=True
    )
    areas["asset_id"] = [f"GEN_AREA_{index + 1:03d}" for index in areas.index]
    areas["label"] = areas["Name"].apply(_clean_label)
    areas["category"] = areas.apply(classify_generation, axis=1)
    areas["area_m2"] = areas.to_crs(METRIC_CRS).area
    areas["is_named"] = ~areas["label"].isin(["Placemark", "unnamed"])

    named_point_assets = points[points["name"].ne("Placemark")].rename(
        columns={"asset_type": "asset_type"}
    )[["asset_id", "name", "asset_type", "geometry"]]
    named_area_assets = _station_points_from_areas(areas)
    generation_sites = gpd.GeoDataFrame(
        pd.concat([named_point_assets, named_area_assets], ignore_index=True),
        geometry="geometry",
        crs=GEOGRAPHIC_CRS,
    ).rename(columns={"asset_id": "generator_id"})
    generation_sites["capacity_mw"] = np.nan
    generation_sites["carrier"] = generation_sites["asset_type"]
    generation_sites["marginal_cost"] = np.nan
    generation_sites["status"] = "needs_validation"
    generation_sites["bus_id"] = pd.NA
    generation_sites["source"] = "collaborator_geometry"
    generation_sites["lon"] = generation_sites.geometry.x
    generation_sites["lat"] = generation_sites.geometry.y

    monthly_peak, annual_demand = extract_demand_workbook(
        input_dir / "power_demand" / "Power Demand.xlsx"
    )

    substation_path = output_dir / "substations.parquet"
    route_path = output_dir / "transmission_routes.parquet"
    point_path = output_dir / "generation_points.parquet"
    area_path = output_dir / "generation_areas.parquet"
    register_path = output_dir / "generation_register_template.csv"
    peak_path = output_dir / "monthly_peak_demand_mw.csv"
    annual_path = output_dir / "annual_sector_demand_gwh.csv"

    substations[["bus_id", "name", "asset_type", "geometry"]].to_parquet(substation_path)
    routes[
        ["route_id", "name", "voltage_kv_hint", "length_km", "geometry"]
    ].to_parquet(route_path)
    points[
        ["asset_id", "name", "asset_type", "PopupInfo", "geometry"]
    ].to_parquet(point_path)
    areas[
        ["asset_id", "label", "category", "area_m2", "is_named", "geometry"]
    ].to_parquet(area_path)
    generation_sites.drop(columns="geometry").to_csv(register_path, index=False)
    monthly_peak.to_csv(peak_path)
    annual_demand.to_csv(annual_path, index=False)

    return PreparedAssets(
        substations=substation_path,
        transmission_routes=route_path,
        generation_points=point_path,
        generation_areas=area_path,
        generation_register_template=register_path,
        monthly_peak_demand=peak_path,
        annual_sector_demand=annual_path,
    )

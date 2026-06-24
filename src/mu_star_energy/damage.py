"""Convert physical damage estimates into the usable share of each asset."""

from __future__ import annotations

import pandas as pd


def damage_to_disruptions(asset_damage: pd.DataFrame) -> pd.DataFrame:
    """Convert estimated damage into the columns expected by the energy model.

    This first version assumes that 30% damage leaves 70% of an asset usable.
    Later work can use different relationships for each hazard and asset type
    and can include repair time.
    """
    required = {"component", "asset_id", "damage_fraction"}
    missing = required - set(asset_damage.columns)
    if missing:
        raise ValueError(f"Asset damage missing columns: {sorted(missing)}")
    if not asset_damage["damage_fraction"].between(0, 1).all():
        raise ValueError("damage_fraction must lie between zero and one")

    disruptions = asset_damage[["component", "asset_id"]].copy()
    disruptions["available_fraction"] = 1 - asset_damage["damage_fraction"]
    return disruptions

"""Translate physical damage outputs into model availability events."""

from __future__ import annotations

import pandas as pd


def damage_to_disruptions(asset_damage: pd.DataFrame) -> pd.DataFrame:
    """Convert damage fractions into the standard simulation input schema.

    This is deliberately simple. Future restoration modelling can replace the
    direct `1 - damage_fraction` relationship with hazard- and asset-specific
    functionality and repair-duration models.
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


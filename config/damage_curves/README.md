# Damage-curve configuration

The energy model needs to know how much of each asset remains usable after an
event. Other parts of mu-star calculate the hazard at each asset and the
resulting physical damage.

`asset_map.csv` links each type of energy asset to an agreed damage
relationship. `curves.csv` stores the points in those relationships. Both files
are intentionally empty until the project agrees the sources, units and values.

The intended conversion is:

```text
hazard at the asset
  -> estimated physical damage
  -> usable share of the asset and repair time
  -> electricity supply calculation during the outage
```

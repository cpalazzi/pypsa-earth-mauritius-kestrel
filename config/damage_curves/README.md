# Damage-curve configuration

The energy model consumes asset availability, while the wider mu-star workflow
calculates hazard intensity and physical damage.

`asset_map.csv` maps energy asset types to damage curves. `curves.csv` stores
curve points. Both files are intentionally empty until project-approved curves
and units are available.

The intended conversion is:

```text
hazard intensity
  -> damage fraction from curve
  -> available fraction / outage duration
  -> fixed-asset PyPSA interruption simulation
```


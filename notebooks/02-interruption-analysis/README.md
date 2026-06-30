# Interruption-analysis notebooks

Purpose: load a saved PyPSA network, run baseline operation, apply
disruptions and write interruption metrics.

Inputs:

- `data/1-processed/energy/networks/<source>.nc`;
- `demand_profile.csv` and `service_weights.csv`, attached to the saved
  topology network before simulation;
- optional disruption tables with `component`, `asset_id` and either
  `available_fraction` or a damage-fraction column.

Outputs:

- baseline and outage metrics;
- unserved-energy tables by bus/substation;
- scenario/disruption tables for review.

Settings users may change: `NETWORK_SOURCE`, solver name and outage cases. Do
not rebuild source-specific network inputs in this stage.

# Interruption-analysis notebooks

Purpose: load a saved PyPSA network handoff, run baseline operation, apply
disruptions and write interruption metrics.

Inputs:

- `data/1-processed/energy/networks/<source>.nc`;
- optional disruption tables with `component`, `asset_id` and either
  `available_fraction` or a damage-fraction column.

Outputs:

- baseline and outage metrics;
- unserved-energy tables by bus/substation;
- scenario/disruption tables for review.

Settings users may change: `NETWORK_SOURCE`, solver name and outage cases. Do
not rebuild source-specific network inputs in this stage.

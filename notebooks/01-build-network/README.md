# Build-Network Notebooks

Purpose: review network inputs, choose `source = "base"` or `"inferred"` and
write a saved PyPSA network handoff under `data/1-processed/energy/networks/`.

Inputs:

- cleaned review tables from `00-data-review`;
- reviewed `lines.csv`, `generators.csv` and `demand_profile.csv` for
  `source = "base"`;
- optional OSM/GridFinder line files, or the PyPSA-Earth OSM fallback, for
  `source = "inferred"`.

Outputs:

- `data/1-processed/energy/networks/base.nc` when reviewed base inputs exist;
- `data/1-processed/energy/networks/inferred.nc` for labelled inferred
  structural scenarios;
- matching metadata JSON and inferred graph review tables.

Settings users may change: `NETWORK_SOURCE`, `ALLOW_PROVISIONAL_DEMAND`,
anchor distance and inferred voltage/capacity assumptions. Provisional demand
is only for structural inferred-network tests.

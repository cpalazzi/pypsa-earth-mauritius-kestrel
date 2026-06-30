# Build-network notebooks

Purpose: review network inputs, choose `source = "base"` or `"inferred"` and
build and save a PyPSA network under `data/1-processed/energy/networks/`.
Notebooks: `00_build_network.ipynb` (the network) and
`01_demand_settings.ipynb` (the demand profile).

Inputs:

- cleaned review tables from `00-data-review`;
- reviewed `lines.csv` and `generators.csv` for `source = "base"`;
- optional OSM/GridFinder line files, or the PyPSA-Earth OSM fallback, for
  `source = "inferred"`.

Outputs:

- `data/1-processed/energy/networks/base.nc` when reviewed base inputs exist;
- `data/1-processed/energy/networks/inferred.nc` derived from OSM/GridFinder routes;
- `data/1-processed/energy/networks/inferred-<region>.nc` when
  `build-network inferred --region <region>` is used;
- matching metadata JSON and inferred graph review tables.

Settings users may change: `NETWORK_SOURCE`, anchor distance and inferred
voltage/capacity assumptions. Demand handling lives in
`01_demand_settings.ipynb` and is attached later during interruption analysis.

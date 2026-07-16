# Build-network notebooks

Purpose: review network inputs, choose `source = "base"` or `"inferred"` and
build and save a PyPSA network under `data/1-processed/energy/networks/`.
Notebooks: `00_build_network.ipynb` (the network) and
`01_demand_settings.ipynb` (the demand profile).

Inputs:

- cleaned review tables from `00-data-review`;
- provided transmission routes, snapped substations and generated
  `generators.csv` for `source = "base"`;
- an `OSM_REGION` (any OSM/Nominatim query) for `source = "inferred"`; its roads
  are fetched from OpenStreetMap and cached, with local GridFinder lines included
  when present. OSM power features are used as roots when cached; otherwise the
  inferred graph uses a provisional road-network root.

Outputs:

- `data/1-processed/energy/networks/base.nc` from prepared provided data;
- `data/1-processed/energy/networks/inferred-<region>.nc` from a region's OSM
  roads, e.g. `build-network inferred --region rodrigues`;
- matching metadata JSON and inferred graph review tables.
- source-specific `generators.csv`, `lines.csv` and `validation.json` under
  `data/2-out/energy/<source>/` for human review.

Settings users may change: `NETWORK_SOURCE`, `OSM_REGION`, `OUTPUT_NAME`,
`OVERWRITE`, `ALLOW_DOWNLOAD` and `OSM_NETWORK_TYPE`. `NETWORK_SOURCE =
"inferred"` rebuilds by default so stale topology files are not loaded. Demand handling lives in
`01_demand_settings.ipynb` and is attached later during interruption analysis.
For a first pipeline run, that notebook writes a clearly labelled one-snapshot
profile from the provided monthly peak table; replace it before interpreting
reliability results.

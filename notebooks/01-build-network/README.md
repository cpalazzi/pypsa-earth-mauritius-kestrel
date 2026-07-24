# Build-network notebooks

Purpose: build or load one selected base, OSM-power inferred, or reviewed-data
inferred topology; validate its NetCDF/GeoParquet parity; and save static and
interactive maps.
Notebooks: `00_build_network.ipynb` (the network) and
`01_demand_settings.ipynb` (the demand profile).

Inputs:

- cleaned review tables from `00-data-review`;
- provided transmission routes, snapped substations and generated
  `generators.csv` for `source = "base"`;
- a region, reviewed VIIRS raster, classified OSM drive roads and an OSM area
  polygon for both inferred sources;
- cached OSM substations, plants and generators for `inferred-osm`;
- reviewed substations and generator sites for `inferred-data`.

Outputs:

- `data/1-processed/energy/networks/<result>/<result>.nc`;
- `data/1-processed/energy/networks/<result>/<result>_metadata.json`;
- a `geoparquet/` subdirectory containing the matching node, edge and manifest
  bundle;
- a `visualisations/` subdirectory containing one static PNG and one
  interactive HTML map;
- `inferred_distribution/` review tables inside an inferred result directory;
- source-specific `generators.csv`, `lines.csv` and `validation.json` under
  `data/2-out/energy/<source>/` for human review.

`00_build_network.ipynb` accepts one `NETWORK_SOURCE`, checks the selected
NetCDF and GeoParquet IDs agree, and plots only that result. Composite inferred
results use regional panels in the single static figure and one pan/zoom HTML
map. Rebuilding and OSM downloads are opt-in, and the final cell lists every
saved path.

Both inferred builds use VIIRS nightlight targets to retain the dense OSM
road subnetwork within the configured support distance while preserving road
cycles. `inferred-osm` treats OSM substations, plants and generators as
terminals but does not invent physical generator capacity. `inferred-data`
uses only reviewed terminals, retains the reviewed CEB backbone, and carries
complete reviewed generator records into PyPSA. The resulting inferred
road-plus-backbone length is compared directly with CEB's reported 10,492.2 km
whole-network circuit length.

Demand handling lives in `01_demand_settings.ipynb` and is attached later
during interruption analysis.
For a first pipeline run, that notebook writes a clearly labelled one-snapshot
profile from the provided monthly peak table; replace it before interpreting
reliability results.

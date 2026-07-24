# Notebooks

Use the repository `.venv` kernel. The notebooks are split by modelling
purpose, not just by data source.

## Fixed-capacity interruption workflow

Run these folders in order after placing provided data under
`data/0-incoming` or an equivalent `MU_STAR_DATA_ROOT`:

1. `00-data-review/` cleans and reviews source data. It does not build a model.
2. `01-build-network/` builds or loads one selected named network, validates
   its NetCDF/GeoParquet bundle, and saves static and interactive maps.
3. `02-interruption-analysis/` loads a saved network and runs baseline/outage cases.

Line capacities and generator details for `source = "base"` come from reviewed
inputs, not from estimates. `inferred-osm` and `inferred-data` are explicitly
labelled nightlight/OSM topology products and remain separate from the reviewed
base network.

For delivery into `nismod/mu-star`, this notebook sequence prepares the inputs
for the `energy` component model. The public call remains
`EnergyModel().simulate(network, disruptions)`, with disruptions provided as
`component`, `asset_id`, and `available_fraction`.

## `pypsa-earth-analysis/`

Notebooks for exploring open-data PyPSA-Earth runs and possible future power
systems. Run only the notebook relevant to your question; they are not a
required sequence. These are a comparison track: they use generic open data
rather than the agreed CEB inventory, and the asset model does not read their
outputs automatically.

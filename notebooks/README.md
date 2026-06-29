# Notebooks

Use the repository `.venv` kernel. The notebooks are split by modelling
purpose, not just by data source.

## `interruption_model/`

Main notebooks for the Mauritius fixed-capacity interruption workflow. Run them
in numeric order after placing collaborator data under `data/0-incoming` or an
equivalent `MU_STAR_DATA_ROOT`. They clean and review the source data, build the
supplied network and run outage cases. The sequence ends with
`02_interruption_analysis.ipynb`, which takes the supplied system tables through
a baseline run and outage cases, mapped onto the mu-star interface of system
data plus disrupted assets. Line capacities and generator details come from
reviewed inputs, not from estimates.

For delivery into `nismod/mu-star`, this notebook sequence prepares the inputs
for the `energy` component model. The public call remains
`EnergyModel().simulate(network, disruptions)`, with disruptions supplied as
`component`, `asset_id`, and `available_fraction`.

## `pypsa_earth/`

Notebooks for exploring open-data PyPSA-Earth runs and possible future power
systems. Run only the notebook relevant to your question; they are not a
required sequence. These are a comparison track: they use generic open data
rather than the agreed CEB inventory, and the asset model does not read their
outputs automatically.

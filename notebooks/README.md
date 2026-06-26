# Notebooks

Use the repository `.venv` kernel. The notebooks are split by modelling
purpose, not just by data source.

## `asset_model/`

Main notebooks for the Mauritius fixed-capacity interruption workflow. Run
these notebooks in numeric order after placing collaborator data under
`data/0-incoming` or an equivalent `MU_STAR_DATA_ROOT`.

These notebooks create and review processed data. They do not estimate missing
line capacities or choose new power stations. The current sequence ends with
`03_interruption_analysis.ipynb`, which follows the path from supplied system
tables to fixed-capacity baseline and outage runs, ties those steps to the
standard mu-star interface of system data plus disrupted assets, and documents
a staged GridFinder-based distribution-network experiment.

## `pypsa_earth/`

Notebooks for exploring open-data PyPSA-Earth runs and possible future power
systems. Run only the notebook relevant to the question; they are not a
required sequence.

These notebooks do not define the agreed CEB asset inventory and their
outputs are not automatically consumed by the asset model.

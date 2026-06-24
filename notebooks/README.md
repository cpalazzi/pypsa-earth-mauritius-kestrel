# Notebooks

Use the repository `.venv` kernel. The notebooks are split by modelling
purpose, not just by data source.

## `asset_model/`

Primary workflow for the Mauritius fixed-asset interruption model. Run these
notebooks in numeric order after placing collaborator data under
`data/0-incoming` or an equivalent `MU_STAR_DATA_ROOT`.

These notebooks create and review processed data. They do not estimate missing
electrical ratings or optimise new capacity.

## `pypsa_earth/`

Reference analyses for open-data PyPSA-Earth builds and solved optimisation
scenarios. Run only the notebook relevant to the question; they are not a
required sequence.

These notebooks do not define the authoritative CEB asset inventory and their
outputs are not automatically consumed by the asset model.

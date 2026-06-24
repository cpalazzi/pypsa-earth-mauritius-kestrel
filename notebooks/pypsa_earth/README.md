# PyPSA-Earth reference notebooks

These notebooks inspect the included PyPSA-Earth model and results for possible
future power systems. They provide an open-data comparison and show how results
change when assumptions change. They are separate from the existing-system
interruption model.

## Prerequisites

- Use the repository `.venv` kernel.
- Keep PyPSA-Earth input and result files under `pypsa-earth/resources`,
  `pypsa-earth/networks`, and `pypsa-earth/results`.
- Sync ARC outputs when a required file is not present locally.
- Check the settings used for each run before comparing results.

## Notebook guide

- `00_cost_inputs_exploration.ipynb`: compare cost sources, units and currency
  years before changing model costs.
- `01_run_analysis.ipynb`: inspect one result's chosen capacities, electricity
  production, energy flows, prices and costs.
- `02_resolution_analysis.ipynb`: compare paired runs that differ only in
  the length of each model time step.
- `03_storage_soc_comparison.ipynb`: compare storage operation and system
  results across a chosen set of runs.
- `04_profiles_analysis.ipynb`: inspect demand, weather-derived renewable
  profiles, land assumptions and the OSM network used by a run.

Common adjustments include file paths, the runs being compared, technologies
shown and plot design. When sharing a comparison, state the model version,
year used for costs, length of each time step, carbon limit or price and which
technologies were available.

# PyPSA-Earth reference notebooks

These notebooks inspect the vendored PyPSA-Earth workflow and its solved
capacity-expansion scenarios. They provide open-data context and sensitivity
analysis; they are separate from the fixed-asset interruption model.

## Prerequisites

- Use the repository `.venv` kernel.
- Keep PyPSA-Earth artifacts under `pypsa-earth/resources`,
  `pypsa-earth/networks`, and `pypsa-earth/results`.
- Sync ARC outputs when a required file is not present locally.
- Check the scenario configuration before comparing results.

## Notebook guide

- `00_cost_inputs_exploration.ipynb`: compare cost sources, units and currency
  years before changing model costs.
- `01_run_analysis.ipynb`: inspect one solved network's capacities, dispatch,
  flows, prices and costs.
- `02_resolution_analysis.ipynb`: compare paired runs that differ only in
  temporal resolution.
- `03_storage_soc_comparison.ipynb`: compare storage operation and system
  metrics across a chosen scenario set.
- `04_profiles_analysis.ipynb`: inspect demand, weather-derived renewable
  profiles, land assumptions and the OSM network used by a run.

Users may change paths, scenario lists, technology subsets and plots. Any
reported comparison must use compatible model versions and clearly state the
cost basis, time resolution, emissions policy and enabled technologies.

# Config

Settings for the energy interruption model (the `mu_star_energy` package):

- `energy.yaml` — data root, solver, value of lost load, and the inferred/OSM
  demand-proxy paths.
- `damage_curves/` — maps each asset type to a damage relationship, used to turn
  hazard damage into asset availability for interruption runs
  (`damage_to_disruptions`).

PyPSA-Earth is configured separately under `pypsa-earth/` (e.g.
`pypsa-earth/config.default.yaml`); this folder does not configure it.

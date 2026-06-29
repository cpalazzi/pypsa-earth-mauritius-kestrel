# Repo Improvement Plan (agent brief)

Goal: bring this repo to a state where the Mauritius energy component model can
be delivered into `nismod/mu-star` (local checkout: `/Users/carlopalazzi/programming/mu-star`)
as the `energy` model, while keeping the standalone asset/interruption workflow
usable. Work top-to-bottom; each phase has acceptance criteria. Do not break the
public call `EnergyModel().simulate(network, disruptions)`.

## Status (2026-06-29)

- 00→01→02 numbering, runner CLI, inferred-distribution graph, delivery notes: done.
- `network_source.py` and `mu-star-energy build-network` now provide the saved
  network handoff for `base` and `inferred` sources.
- Current local generation:
  - source review tables regenerated under `data/1-processed/energy/collaborator/`;
  - reviewed `base` network attempted but blocked until `lines.csv`,
    `generators.csv`, and `demand_profile.csv` are supplied;
  - structural `inferred` network generated at
    `data/1-processed/energy/networks/inferred.nc` using the local PyPSA-Earth
    OSM line extraction fallback and provisional one-snapshot demand.
- Notebook restructuring around the network-source selector is done: notebooks
  now live under `00-data-review/`, `01-build-network/`, and `02-interruption-analysis/`; the
  network notebook calls `build_network(source=...)`; the interruption notebook
  loads `networks/<source>.nc`.
- Next: replace provisional inferred inputs with cached OSM/GridFinder and
  reviewed demand/generator tables, then add island-specific OSM ingestion.

## Context: the mu-star delivery target

- Component models live at `src/<model_name>/` and expose `simulate(network, disruptions) -> metrics`
  (see `src/transport/model.py::SampleModel`). Our model is `EnergyModel.simulate`
  in `src/mu_star_energy/model.py` — keep this signature; return value is
  `SimulationResult(metrics: dict, network)`.
- Disruption table columns here: `component`, `asset_id`, `available_fraction`
  (`apply_disruptions`). mu-star damage produces `fraction`/`monetary`; we map
  `available_fraction = 1 - damage_fraction` in `damage.damage_to_disruptions`.
- Data stages: mu-star uses `incoming/processed/out`; we use `0-incoming/1-processed/2-out`.
  Keep our numbered names locally but document the mapping; do not rename yet.
- mu-star targets Python ≥3.12; confirm our `pyproject.toml` is compatible before delivery.

## Naming conventions (decided)

- `notebooks/asset_model/` was renamed to `notebooks/interruption_model/`, then
  split by lifecycle stage (see restructure below): `00-data-review/`,
  `01-build-network/`, `02-interruption-analysis/`, alongside `pypsa-earth/`.
- `existing_lines.csv` → `lines.csv`, `existing_generators.csv` → `generators.csv`
  (within this model every asset is "existing", so the prefix is noise). Already
  applied to code, config, tests and docs; the notebook restructure below must
  adopt the same names and drop `existing_*` variables.

## The two models

- **Interruption model** (`src/mu_star_energy`; notebooks `00-data-review`,
  `01-build-network`, `02-interruption-analysis`): fixed-capacity dispatch + outage analysis.
  The mu-star deliverable.
- **PyPSA-Earth** (`pypsa-earth/`, `notebooks/pypsa-earth`): open-data build,
  demand/weather/renewable methods, and capacity expansion. Present so the
  interruption model can borrow methods (e.g. demand profiles) and as the
  natural home for a future **capacity-expansion** extension. Keep the two
  separate; expansion never runs inside the interruption simulator
  (`assert_fixed_capacity` stays).

## Notebook restructure (agent brief)

Decision: split notebooks by lifecycle stage. The network is a shared artifact;
interruption is one analysis over it (capacity expansion will be another). The
handoff between stages is a saved PyPSA network file, so no notebook depends on
another's in-memory state. One builder takes a `source` setting; both tracks
converge on `EnergyModel.simulate`.

```
notebooks/
  00-data-review/   look only: CEB shapefiles + OSM/GridFinder, maps, tables. No model.
  01-build-network/ build source = base | inferred (per island); fetch OSM/GridFinder if
                   absent; emit lines/buses/generators/demand -> PyPSA network; save .nc.
  02-interruption-analysis/  load a saved network, baseline + outage cases, write metrics.
  pypsa-earth/     open-data reference; future capacity-expansion analysis.
```

- Migrate today's notebooks with `git mv`: `00_data_review` -> `00-data-review/`,
  `01_build_network` -> `01-build-network/` (the build notebook),
  `02_interruption_analysis` -> `02-interruption-analysis/`.
- Handoff artifact: `data/1-processed/energy/networks/<source>[-<island>].nc`.
  `01-build-network` writes it; `02-interruption-analysis` loads it and never branches on source.
- Keep numeric folder prefixes + a top-level `notebooks/README.md` run order.
  Islands and scenarios are parameters inside `01-build-network`, not extra folders.
### Done in commit 10cf6a4
- `network_source.py` + `build-network base|inferred` CLI + Snakemake rules
  `build_base_network` / `build_inferred_network` save `<source>.nc` + metadata
  to `data/1-processed/energy/networks/`.
- Inferred graph → PyPSA tables convergence works; `base` blocked only on the
  three reviewed CSVs (`lines`/`generators`/`demand_profile`).
- `osmnx>=2` added to `pyproject.toml`; `network.py` lines carry an `AC` carrier
  and a small resistance.

### 1. Notebook restructure (done)
- The three notebooks were migrated into staged folders:
  `00-data-review/`, `01-build-network/`, and `02-interruption-analysis/`.
- Notebook contents use `lines.csv` / `generators.csv`; `01-build-network` drives
  `build_network(source=...)`; `02-interruption-analysis` loads a saved `.nc` and does
  not rebuild.
- `run-interruptions` accepts `--network` / `--network-source` and the
  Snakemake run rules consume `networks/base.nc`.

### 2. Real OSM ingestion + islands (NOT done — osmnx unused)
- Add `osm.py` (osmnx/Overpass), cache to `0-incoming/energy/osm/<island>/`:
  roads, `power=line/cable`, generators/substations, buildings. Per island
  (Rodrigues, Agalega, St Brandon — near-empty, handle gracefully) via an
  `--island` option; build one isolated inferred network each. Today the
  inferred build only uses passed files or the mainland PyPSA-Earth OSM
  fallback, so make osmnx the primary path.

### 3. Transformers + voltage levels (NOT done)
- Inferred is currently flat single-voltage (`inferred_voltage_kv`, default 11)
  with generators attached to distribution nodes. Add transformer/voltage
  support to `network.py` (AC-lines-only today) so distribution hangs under
  transmission. Capacities are estimates → low/base/high sets, `inferred` flag,
  never in base.

### 4. First-pass docs
- One README per notebook folder is in place; top-level README and
  DEVELOPMENT_NOTES describe the staged notebook workflow.

Acceptance: `01-build-network` builds base or any island inferred grid and saves a
network; `02-interruption` loads any saved network unchanged; tests green.

## Delivery prep

- Mirror `src/transport/` layout; confirm `simulate` metrics; stage rename
  `0-incoming/1-processed/2-out` → `incoming/processed/out` at move time.

## Guardrails

- Never let the model build new capacity (`assert_fixed_capacity` must pass).
- Don't add GridFinder/inferred lines to the electrical calc as real assets.
- Keep `EnergyModel.simulate(network, disruptions)` stable; clear notebook
  outputs before commit; keep source files in `0-incoming` unchanged.

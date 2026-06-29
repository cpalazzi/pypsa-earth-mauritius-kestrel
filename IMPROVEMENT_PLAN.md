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
- Next: finish notebook restructuring around the network-source selector and
  replace provisional inferred inputs with cached OSM/GridFinder and reviewed
  demand/generator tables.

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
  split by lifecycle stage (see restructure below): `0-data_review/`,
  `1-network/`, `2-interruption/`, alongside `pypsa_earth/`.
- `existing_lines.csv` → `lines.csv`, `existing_generators.csv` → `generators.csv`
  (within this model every asset is "existing", so the prefix is noise). Already
  applied to code, config, tests and docs; the notebook restructure below must
  adopt the same names and drop `existing_*` variables.

## The two models

- **Interruption model** (`src/mu_star_energy`; notebooks `0-data_review`,
  `1-network`, `2-interruption`): fixed-capacity dispatch + outage analysis.
  The mu-star deliverable.
- **PyPSA-Earth** (`pypsa-earth/`, `notebooks/pypsa_earth`): open-data build,
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
  0-data_review/   look only: CEB shapefiles + OSM/GridFinder, maps, tables. No model.
  1-network/       build source = base | inferred (per island); fetch OSM/GridFinder if
                   absent; emit lines/buses/generators/demand -> PyPSA network; save .nc.
  2-interruption/  load a saved network, baseline + outage cases, write metrics.
  pypsa_earth/     open-data reference; future capacity-expansion analysis.
```

- Migrate today's notebooks with `git mv`: `00_data_intake` -> `0-data_review/`,
  `01_operational_network` -> `1-network/` (becomes the build notebook),
  `02_interruption_analysis` -> `2-interruption/`.
- Handoff artifact: `data/1-processed/energy/networks/<source>[-<island>].nc`.
  `1-network` writes it; `2-interruption` loads it and never branches on source.
- Keep numeric folder prefixes + a top-level `notebooks/README.md` run order.
  Islands and scenarios are parameters inside `1-network`, not extra folders.
### Done in commit 10cf6a4
- `network_source.py` + `build-network base|inferred` CLI + Snakemake rules
  `build_base_network` / `build_inferred_network` save `<source>.nc` + metadata
  to `data/1-processed/energy/networks/`.
- Inferred graph → PyPSA tables convergence works; `base` blocked only on the
  three reviewed CSVs (`lines`/`generators`/`demand_profile`).
- `osmnx>=2` added to `pyproject.toml`; `network.py` lines carry an `AC` carrier
  and a small resistance.

### 1. Notebook restructure (NOT done — main remaining task)
- Migrate the three notebooks out of `notebooks/interruption_model/` into staged
  folders with `git mv`: `00_data_intake` → `0-data_review/`,
  `01_operational_network` → `1-network/`, `02_interruption_analysis` →
  `2-interruption/`. Delete the stray untracked `notebooks/asset_model/`.
- Update notebook **contents**: they still reference `existing_lines.csv` /
  `existing_generators.csv` and the old variables — rename to `lines.csv` /
  `generators.csv`. `1-network` drives `build_network(source=...)`;
  `2-interruption` loads a saved `.nc` and never rebuilds.
- Make `run-interruptions` / `2-interruption` consume `networks/<source>.nc`
  instead of rebuilding from CSVs (runner currently rebuilds).

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
- One README per notebook folder (Purpose/Inputs/Outputs/Settings); update
  top-level README + DEVELOPMENT_NOTES module map; clear outputs before commit.

Acceptance: `1-network` builds base or any island inferred grid and saves a
network; `2-interruption` loads any saved network unchanged; tests green.

## Delivery prep

- Mirror `src/transport/` layout; confirm `simulate` metrics; stage rename
  `0-incoming/1-processed/2-out` → `incoming/processed/out` at move time.

## Guardrails

- Never let the model build new capacity (`assert_fixed_capacity` must pass).
- Don't add GridFinder/inferred lines to the electrical calc as real assets.
- Keep `EnergyModel.simulate(network, disruptions)` stable; clear notebook
  outputs before commit; keep source files in `0-incoming` unchanged.

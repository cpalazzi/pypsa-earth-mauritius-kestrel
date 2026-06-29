# Repo Improvement Plan (agent brief)

Goal: bring this repo to a state where the Mauritius energy component model can
be delivered into `nismod/mu-star` (local checkout: `/Users/carlopalazzi/programming/mu-star`)
as the `energy` model, while keeping the standalone asset/interruption workflow
usable. Work top-to-bottom; each phase has acceptance criteria. Do not break the
public call `EnergyModel().simulate(network, disruptions)`.

## Status (2026-06-29)

- Phase 1 (notebook numbering): done — sequence is 00→01→02.
- Phase 2 (developer notes): done — delivery, schema and module map documented.
- Phase 3 (runnable model): done — `run-interruptions` CLI + Snakemake rules
  consume `demand_profile.csv`; optional generator availability supported.
- Phase 4 (synthetic distribution): done — `distribution_network.py` builds the
  flagged GridFinder/OSM graph and downstream-disconnection impacts.
- Phase 5 (validation + delivery) and real CEB data: outstanding.

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

## Phase 1 — Fix notebook numbering (do first, mechanical)

Current: `notebooks/asset_model/00_data_intake`, `01_operational_network`,
`03_interruption_analysis` (gap at 02; any `*_draft.ipynb` is stale).

1. Rename `03_interruption_analysis.ipynb` -> `02_interruption_analysis.ipynb`
   with `git mv` (preserve history).
2. Delete any leftover `03_interruption_analysis_draft.ipynb` only if it has no
   unique content; otherwise fold useful cells into `02_` first.
3. Grep-and-update every reference: `grep -rn "03_interruption_analysis"` across
   `README.md`, `notebooks/README.md`, `notebooks/asset_model/README.md`, the
   notebook intro cells, and `tests/`. Update titles inside notebook cells too.
4. Acceptance: numeric sequence is 00→01→02; no dangling refs; `pytest` green.

## Phase 2 — Developer notes refresh

Update `DEVELOPMENT_NOTES.md` and per-folder READMEs to reflect current state:

- State delivery target explicitly: package `mu_star_energy` → mu-star `src/energy`,
  data-stage name mapping, disruption-schema mapping. Add a "Delivery to mu-star"
  section with the interface, dependency, and Python-version checklist.
- Trim repeated defensive negations; keep limitation notes only where factual.
- Add a short "module map": `intake.py`, `network.py`, `model.py`, `damage.py`,
  `distribution.py`, `paths.py`, `cli.py` — one line each.
- Acceptance: a new contributor can find the interface and run intake→sim from
  the notes alone.

## Phase 3 — Complete a runnable existing-system model

Blocking gaps to close (already listed in DEVELOPMENT_NOTES priorities 1–4):

1. `demand_profile.csv` is checked but not consumed by the workflow. Add a CLI
   command + Snakemake rule to read it, validate timestamps/units, build the
   network via `build_operational_network`, run baseline, write to `data/2-out`.
2. Generator availability over time: extend `build_operational_network` to accept
   optional per-generator/per-snapshot availability; wire wind/solar to ERA5
   profiles already in `pypsa-earth/resources/mauritius-year-1/`.
3. Acceptance: baseline run completes with no load-shedding; outage run produces
   `unserved_energy_mwh` > 0; results saved under `data/2-out/energy/`.

## Phase 4 — Distribution network draft (OpenGridFinder)

Today `distribution.py` only assigns demand shares by nearest-line length. Add a
SYNTHETIC distribution layer kept out of the reviewed baseline:

1. Ingest OpenGridFinder lines into `data/0-incoming/energy/gridfinder/`; keep a
   `source` column to separate GridFinder estimates from OSM/CEB.
2. New module `src/mu_star_energy/distribution_network.py`:
   - build a graph from GridFinder + OSM segments, anchor feeders to reviewed
     substations with a documented snap threshold;
   - load nodes by population/building proxy.
3. Stage A (do first): graph connectivity + downstream disconnection only —
   when a bus/feeder is cut, count demand lost, no power flow.
4. Stage B (later): power flow needs separate voltage buses + transformers and
   named sensitivity sets for feeder capacity/impedance. Gate behind a flag.
5. Label everything `synthetic`; never merge into the CEB baseline. Add tests.
6. Acceptance: a scenario flag builds the synthetic layer; baseline unchanged.

## Phase 5 — Validation & delivery prep

- Reconcile annual/peak/sector demand vs CEB; capacity factors vs reports.
- Mirror `src/transport/` layout; confirm `simulate` returns the metrics
  mu-star expects; add `src/<model>/tests/`.
- Document copy/move path: `mu_star_energy` → `mu-star/src/energy`, stage rename
  `0-incoming/1-processed/2-out` → `incoming/processed/out`.

## Guardrails

- Never let the model build new capacity (`assert_fixed_capacity` must pass).
- Don't add GridFinder/synthetic lines to the electrical calc as real assets.
- Keep `EnergyModel.simulate(network, disruptions)` stable; clear notebook
  outputs before commit; keep source files in `0-incoming` unchanged.

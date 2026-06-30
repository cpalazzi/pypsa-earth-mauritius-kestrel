# Mauritius energy network model

The Mauritius electricity component of the
[`mu-star`](https://github.com/nismod/mu-star) infrastructure risk workflow. It
measures how much demand goes unserved when existing energy assets are damaged
or taken out of service: for each hour it dispatches the available power
stations to meet demand and reports unserved energy, the share of demand served
and operating cost.

This is an operational model of a fixed set of assets — it does not size or site
new generation, lines or storage.

## Two tracks

**Interruption model (primary)** — code in `src/mu_star_energy/`, notebooks in
`notebooks/00-data-review/`, `01-build-network/` and `02-interruption-analysis/`. Runs a
provided system and tests asset outages:

```text
source data -> reviewed tables -> PyPSA network -> outage cases -> unserved energy
```

The standard call is:

```python
result = EnergyModel().simulate(network, disruptions)
```

**PyPSA-Earth reference** — code in `pypsa-earth/`, notebooks in
`notebooks/pypsa-earth-analysis/`. An open-data build used for renewable profiles, GEGIS
demand and capacity-expansion comparisons. It is not the CEB asset record and
does not feed the interruption model.

## Repository layout

The energy interruption model (the deliverable) and a vendored PyPSA-Earth
reference sit side by side. Everything at the top level belongs to the energy
model except `pypsa-earth/`, `arc/` and `references/`.

```text
# Energy interruption model — delivered to mu-star as the `energy` component
├── src/mu_star_energy/      # Model code
├── config/                  # Model settings (energy.yaml) and damage curves
├── workflow/                # Snakemake preparation/run rules
├── data/                    # Model data: 0-incoming -> 1-processed -> 2-out
├── tests/
├── notebooks/
│   ├── 00-data-review/
│   ├── 01-build-network/
│   └── 02-interruption-analysis/

# PyPSA-Earth reference — vendored, with its own config/data inside
├── pypsa-earth/             # Vendored PyPSA-Earth code and outputs
├── arc/                     # Scripts to run PyPSA-Earth on the ARC cluster
├── references/              # Reference data sheets
└── notebooks/pypsa-earth-analysis/   # Notebooks exploring PyPSA-Earth runs
```

The energy model's `config/`, `workflow/`, `data/` and `src/` mirror the mu-star
component layout. PyPSA-Earth keeps its own `config/`, `data/`, `resources/` and
`results/` inside `pypsa-earth/`. Within `data/`, the numeric prefixes just keep
the stages sorted in a file browser.

## Glossary

- **Bus** — a connection point; here, a substation.
- **Dispatch** — how much each station produces in a time step.
- **Snapshot** — one model time step (e.g. an hour).
- **Service weight** — a substation's share of total demand (shares sum to one).
- **Unserved energy / load shedding** — demand the system could not supply.

## Capacity conventions

- `capacity_mw` is electrical output in `MW_e` and maps to PyPSA
  `Generator.p_nom` (not fuel input; no LHV conversion).
- `marginal_cost` is per `MWh_e`. For a thermal fuel priced per `MWh_fuel`
  (LHV), convert first — `fuel price / efficiency + variable operating cost` —
  and record the basis in `fuel_energy_basis`.
- `s_nom_mva` is a line's apparent-power rating in MVA; `v_nom_kv` is nominal
  voltage in kV.

The builder creates AC `Line` and `Generator` components only. See the
[PyPSA 0.30.3 components](https://docs.pypsa.org/v0.30.3/user-guide/components.html).

## Setup

```bash
./local_setup.sh
source .venv/bin/activate
pip install -e .
```

Use the `.venv` kernel for notebooks. Check the install with `.venv/bin/pytest`.

## Workflow

1. **Place source data** under `data/0-incoming/energy/provided/` (the
   `power_demand`, `power_transmission`, `substation` and `generation_source`
   folders described in `data/0-incoming/README.md`). Keep source files
   unchanged. To use a shared or OneDrive tree, set `MU_STAR_DATA_ROOT` to a
   directory with the same numbered stage folders.

2. **Prepare review tables:**

   ```bash
   .venv/bin/python -m mu_star_energy.cli prepare-assets
   ```

   This writes cleaned tables to `data/1-processed/`. Don't edit generated
   Parquet files by hand.

3. **Run the notebooks in order:** `00-data-review/` (clean and inspect source
   data), `01-build-network/` (build a saved network), `02-interruption-analysis/` (run
   baseline and outage cases).

4. **Build a network** (what `01-build-network/` calls):

   ```bash
   .venv/bin/python -m mu_star_energy.cli build-network base
   ```

   `base` needs the reviewed topology inputs below and fails rather than
   guessing missing values. `build-network inferred` writes a topology-only
   network derived from OSM roads (the GridFinder approach), for testing before
   reviewed data exists. For an outer-island build, use
   `build-network inferred --island rodrigues`.

5. **Run interruptions:**

   ```bash
   .venv/bin/python -m mu_star_energy.cli run-interruptions \
     --network data/1-processed/energy/networks/base.nc \
     --output-dir data/2-out/energy \
     --disruptions data/1-processed/energy/provided/disruptions.csv
   ```

   Omit `--disruptions` for a baseline-only run. Results and a `demand_summary.csv`
   are written under `data/2-out/energy/`. Equivalently, call
   `EnergyModel().simulate(network, disruptions)` in Python.

### Reviewed inputs for `base`

Place these under `data/1-processed/energy/provided/`:

- `lines.csv` — `line_id`, `bus0`, `bus1`, `v_nom_kv`, `length_km`, `s_nom_mva`.
  Must come from CEB records: `PowerGrid.shp` geometry has no line endpoints or
  ratings, so connections are never inferred from route proximity.
- `generators.csv` — `generator_id`, `bus_id`, `carrier`, `capacity_mw`,
  `marginal_cost` (start from the generated register template).
- `service_weights.csv` — each substation's share of demand (shares sum to one).
- `demand_profile.csv` — required when running interruptions, not when building
  the topology network. Use a timestamp column plus either one `demand_mw`
  column (split across substations by `service_weights.csv`) or one column per
  `bus_id`. Regular half-hourly, hourly or three-hourly spacing.

The provided workbook only provides monthly peaks and annual sector totals,
so a dated `demand_profile.csv` must come from CEB or another documented source.

## Distribution network

The low-voltage distribution network is unavailable, so it is not part of the
electrical calculation. OSM and GridFinder lines are used only to estimate each
substation's share of demand by nearest-line length. The `inferred` network
build derives a network from those OSM roads (the GridFinder approach), kept
labelled and separate — never merged into the reviewed `base` inputs.

## Guardrails

- Don't modify source files in `data/0-incoming/`.
- Don't present inferred lines, GridFinder routes or polygon sizes as confirmed
  CEB data.
- Don't let the interruption model build new generation, lines or storage.
- If you rename an asset ID, keep a table mapping old to new.

## PyPSA-Earth comparisons

See `notebooks/pypsa-earth-analysis/README.md`. These notebooks are read-only analysis:
pick the one relevant to your question and confirm compared runs share the same
assumptions (cost year, time-step length, carbon limit, technologies).

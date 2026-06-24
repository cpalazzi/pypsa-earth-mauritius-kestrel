# Mauritius Energy Network Model

This repository develops the Mauritius electricity component model for the
[`mu-star`](https://github.com/nismod/mu-star) infrastructure risk workflow.
Its primary purpose is to measure service interruption when existing energy
assets are damaged or unavailable.

The core model is **not a capacity-expansion model**. It represents the
currently installed generation, transmission lines, substations and calibrated
demand in PyPSA, fixes their capacities, then redispatches the system under
asset outages. Results include unserved energy, served demand and operating
cost.

## Choose The Modelling Track

### 1. Asset-level interruption model

Use this track to represent the existing Mauritius electricity system and test
asset outages. This is the primary project workflow. The code is under
`src/mu_star_energy/`; the guided review notebooks are under
`notebooks/asset_model/`.

```text
collaborator and open source data
  -> processed asset tables and topology
  -> fixed-capacity PyPSA network
  -> hazard/damage-derived asset availability
  -> operational redispatch and service-loss metrics
```

This follows the mu-star interface:

```python
result = EnergyModel().simulate(network, disruptions)
```

Inputs are a PyPSA network and a table of disrupted generators, lines or
substations. Capacity expansion is explicitly rejected.

### 2. PyPSA-Earth reference track

Use this track to inspect a generic open-data PyPSA-Earth build, renewable
profiles, capacity-expansion results, and scenario sensitivities. The vendored
workflow is under `pypsa-earth/`; its analysis notebooks are under
`notebooks/pypsa_earth/`.

This track is useful for:

- open-data transmission topology;
- ERA5 renewable profiles;
- generic GEGIS demand;
- comparison with a standard PyPSA-Earth capacity-optimisation run.

It is not the authoritative representation of existing CEB assets and does not
feed the interruption model automatically. Hydrogen, ammonia and greenfield
expansion scenarios are optional reference cases.

## Repository Layout

```text
├── src/mu_star_energy/          # Fixed-asset model and preprocessing package
├── config/energy.yaml           # Model paths and operational assumptions
├── config/damage_curves/        # Damage-curve mapping placeholders
├── workflow/                    # mu-star-style Snakemake stages
├── notebooks/
│   ├── asset_model/             # Main data/topology/readiness notebooks
│   └── pypsa_earth/             # Baseline/reference notebooks
├── data/
│   ├── 0-incoming/              # Raw OneDrive, OSM and GridFinder inputs
│   ├── 1-processed/             # Reproducible analysis-ready assets
│   └── 2-out/                   # Disruption results
├── pypsa-earth/                 # Vendored reference workflow and its outputs
├── arc/                         # PyPSA-Earth ARC scripts
└── DEVELOPMENT_NOTES.md
```

The root project has one ordered data tree. The numeric prefixes only make the
stages sort correctly in an IDE. PyPSA-Earth's own `data/`, `resources/`,
`networks/`, and `results/` stay inside the vendored `pypsa-earth/` directory.

## First-Time Setup

Use the repository virtual environment:

```bash
./local_setup.sh
source .venv/bin/activate
pip install -e .
```

Use the `.venv` kernel when opening notebooks. Verify the installation with:

```bash
.venv/bin/pytest
```

## Asset Model Workflow

### 1. Place source data

The default collaborator input directory is:

```text
data/0-incoming/energy/collaborator/
```

It must contain the expected `power_demand`, `power_transmission`,
`substation`, and `generation_source` folders described in
`data/0-incoming/README.md`. Keep received files and filenames unchanged.

To use a shared or OneDrive-synchronised data tree instead, set
`MU_STAR_DATA_ROOT`. That directory must contain the same numbered stage
folders:

```bash
export MU_STAR_DATA_ROOT="/path/to/shared/mu-star-data"
```

### 2. Build processed assets and topology

```bash
.venv/bin/python -m mu_star_energy.cli prepare-assets
.venv/bin/python -m mu_star_energy.cli build-topology
```

Equivalent Snakemake target:

```bash
.venv/bin/snakemake \
  --snakefile workflow/Snakefile \
  --cores 1 \
  data/1-processed/energy/network/topology_report.json
```

These commands may overwrite generated files under `data/1-processed`.
Do not manually edit generated Parquet files.

### 3. Review and complete the model

Open the notebooks in this order:

1. `notebooks/asset_model/00_data_intake.ipynb`
2. `notebooks/asset_model/01_operational_network.ipynb`

The first checks source coverage and creates the generation register template.
The second reviews the provisional transmission topology, optional distribution
proxy, and operational readiness gate.

Before interruption simulation, the user must supply or validate:

- stable substation and branch identifiers, names and voltage classes;
- line and transformer thermal ratings;
- `existing_generators.csv`, based on the generated register template, with
  `generator_id`, `bus_id`, `carrier`, `capacity_mw`, and `marginal_cost`
  populated and supported by CEB/technical sources;
- a dated `demand_profile.csv` with timestamps and nodal demand;
- reviewed service weights for allocating system demand to substations;
- approved damage curves and restoration assumptions.

`demand_profile.csv` may contain one system column named `demand_mw`, which is
allocated using `service_weights.csv`, or one complete column per `bus_id`.
Its index must be parseable as timestamps. Service weights must cover every bus
and sum to one.

### 4. Run interruption scenarios

Once the readiness inputs are complete, build a fixed-capacity PyPSA network
and call:

```python
result = EnergyModel().simulate(network, disruptions)
```

Write scenario results beneath `data/2-out/energy/`.

## Allowed Changes

Users may change:

- the data root through `MU_STAR_DATA_ROOT`;
- topology snap tolerance and provisional default voltage in
  `config/energy.yaml`;
- optional OSM/GridFinder inputs and the service-weight method;
- solver, value of lost load, scenario definitions and damage assumptions;
- source adapters, provided schema changes are explicit and provenance is
  retained.

Users must not:

- modify received source files in `data/0-incoming`;
- treat inferred topology, GridFinder lines or polygon areas as validated
  electrical parameters;
- change or recycle stable asset IDs without a documented crosswalk;
- enable extendable generation, line, link or storage capacity in the
  interruption model;
- mix PyPSA-Earth optimisation outputs into the fixed-asset model without an
  explicit, reviewed conversion step.

## Distribution-Network Treatment

The real distribution network is unavailable. We therefore keep it outside the
electrical power-flow representation:

- OSM distribution lines provide mapped evidence where available;
- GridFinder provides inferred network routes based on night lights and roads;
- combined line length is assigned to the nearest substation to estimate
  service-area/demand weights.

This proxy supports customer-impact allocation, not voltage, conductor,
protection or distribution power-flow analysis. GridFinder routes must not be
presented as observed infrastructure.

## PyPSA-Earth Reference Workflow

Start with `notebooks/pypsa_earth/README.md`. These notebooks are read-only
analysis tools unless a notebook explicitly states otherwise. Users are
expected to select or sync the required network/profile files and verify that
compared scenarios use compatible configurations. Scenario paths, technology
subsets and plotting choices are flexible; the underlying input provenance,
currency year, temporal resolution and scenario assumptions must remain
visible in any reported comparison.

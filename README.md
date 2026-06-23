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

## Two Modelling Tracks

### 1. Asset-level interruption model

The main project code is under `src/mu_star_energy/`.

```text
incoming source data
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

### 2. PyPSA-Earth baseline

The vendored `pypsa-earth/` workflow and notebooks under
`notebooks/pypsa_earth/` are retained as a reference for:

- open-data transmission topology;
- ERA5 renewable profiles;
- generic GEGIS demand;
- comparison with a standard PyPSA-Earth capacity-optimisation run.

They are not the authoritative mu-star interruption model. Hydrogen, ammonia
and greenfield expansion scenarios are legacy comparison cases.

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
│   ├── incoming/                # Raw OneDrive, OSM and GridFinder inputs
│   ├── processed/               # Reproducible analysis-ready assets
│   └── out/                     # Disruption results
├── pypsa-earth/                 # Vendored baseline workflow and its outputs
├── arc/                         # Legacy PyPSA-Earth ARC scripts
└── DEVELOPMENT_NOTES.md
```

The root project has one data tree. `incoming`, `processed`, and `out` are
lifecycle stages, not separate data stores. PyPSA-Earth's own `data/`,
`resources/`, `networks/`, and `results/` stay inside the vendored
`pypsa-earth/` directory.

Project data contents are ignored by git. Set `MU_STAR_DATA_ROOT` to use a
shared OneDrive-synchronised or other external data directory:

```bash
export MU_STAR_DATA_ROOT="/path/to/shared/mu-star-data"
```

Without that variable, the repository-local `data/` directory is used.

## Environment

Use the repository virtual environment:

```bash
./local_setup.sh
source .venv/bin/activate
pip install -e .
```

Run tests:

```bash
.venv/bin/pytest
```

## Prepare Current Collaborator Data

```bash
.venv/bin/python -m mu_star_energy.cli prepare-assets
.venv/bin/python -m mu_star_energy.cli build-topology
```

Equivalent Snakemake target:

```bash
.venv/bin/snakemake \
  --snakefile workflow/Snakefile \
  --cores 1 \
  data/processed/energy/network/topology_report.json
```

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

## Readiness Before Interruption Runs

The current data supports asset mapping and provisional topology. A defensible
operational simulation still requires:

- explicit names and voltage classes for substations and line segments;
- validated line/transformer thermal ratings;
- a CEB-reconciled existing generation register with capacities and fuels;
- generator-to-substation assignments;
- calibrated hourly or half-hourly demand;
- OSM/GridFinder service weights or another agreed nodal demand allocation;
- project-approved hazard damage curves and restoration assumptions.

Until these fields are complete, the workflow intentionally stops before
operational simulation rather than optimising missing capacities.

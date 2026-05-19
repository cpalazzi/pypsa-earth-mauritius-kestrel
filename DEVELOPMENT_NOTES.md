# PyPSA-Earth Mauritius Kestrel - Development Notes

## Purpose

This repo is a working PyPSA-Earth fork for Mauritius electricity-system modelling. It was initialized from `pypsa-earth-green-auklet` to preserve the proven local setup, ARC workflow, DEA cost references, analysis notebooks, and hydrogen/ammonia extension code. The active configs are now Mauritius-specific.

## Current Modelling Scope

- Country: Mauritius (`MU`)
- Base network: up-to-12-node default aggregation (`clusters: ["12flex"]`)
- Weather/load year: 2013 weather year with 2030 planning horizon
- Default run: `mauritius-year-1`, standard electricity technologies only
- Extension runs: H2 and NH3 are retained for later comparison, not the first modelling focus
- Cost basis: upstream default costs for baseline; DEA 2030 costs for `*-dea30` variants

## Scenario Naming

Use `config.<region>-<timespan>-<nodes>[-variant].yaml`.

- `config.mauritius-year-1-profiles.yaml` builds annual renewable profiles.
- `config.mauritius-year-1.yaml` is the standard-tech baseline.
- `config.mauritius-week-1.yaml` is the smoke test using annual profile resources.
- `config.mauritius-year-1-co2-zero-dea30.yaml` is the zero-CO2 standard-tech case.
- `config.mauritius-year-1-h2-dea30.yaml` enables H2.
- `config.mauritius-year-1-nh3-dea30.yaml` enables H2 and NH3.

All solve variants intentionally share `run.name: mauritius-year-1` to reuse:

- `resources/mauritius-year-1/`
- `networks/mauritius-year-1/`
- `results/mauritius-year-1/`

Do not submit solve variants with the same `run.name` at the same time. Chain them with SLURM dependencies because Snakemake locks the workdir and the scenario-specific `_ec.nc` intermediates are rebuilt per config.

## ARC Paths

Expected ARC layout:

```text
/data/<group>/<user>/
├── pypsa-earth-mauritius-kestrel/
│   ├── pypsa-earth/
│   ├── arc/
│   ├── notebooks/
│   └── results/
├── envs/
└── licenses/
```

Default local ARC values in scripts still target the Oxford project area:

- group: `engs-df-green-ammonia`
- user default: current `$USER`
- environment: `/data/<group>/<user>/envs/pypsa-earth-env`

Override with environment variables where needed, for example `ARC_PYPSA_ENV`, `ARC_WORKDIR`, `ARC_GROUP`, or `ARC_REPO_URL`.

## ARC SSH Socket

At the start of each working session, open a reusable ARC SSH control socket from a normal local terminal where you can enter the ARC password:

```bash
ssh -M -S ~/.ssh/arc-oxford-codex.sock -fnNT arc-oxford
```

Codex can then reuse that socket non-interactively:

```bash
ssh -S ~/.ssh/arc-oxford-codex.sock -o BatchMode=yes arc-oxford 'hostname'
```

Use the same socket for `rsync`:

```bash
rsync -az -e "ssh -S $HOME/.ssh/arc-oxford-codex.sock -o BatchMode=yes" \
  ./ arc-oxford:/data/engs-df-green-ammonia/engs2523/pypsa-earth-mauritius-kestrel/
```

If ARC returns `Permission denied` or the socket path is missing, recreate the socket in a local terminal before asking Codex to run ARC commands. Do not type the ARC password into Codex.

## Local Analysis Environment

Create the repo-local Python environment with:

```bash
./local_setup.sh
source .venv/bin/activate
```

Use the repo-root `.venv` and Jupyter kernel `pypsa-earth-mauritius-kestrel` (`Python (PyPSA-Earth Mauritius)`) for the analysis notebooks. Do not copy `.venv` from another PyPSA-Earth checkout; compiled geospatial dependencies and kernel paths are repo- and machine-specific.

## ARC Run Sequence

From `pypsa-earth/`:

```bash
sbatch ../arc/jobs/01_build_profiles.sh \
  mauritius-year-1-profiles \
  configs/scenarios/config.mauritius-year-1-profiles.yaml
```

Check required profile files:

```bash
../arc/arc_check_run_inputs.sh configs/scenarios/config.mauritius-year-1.yaml
```

Submit the baseline:

```bash
sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 \
  configs/scenarios/config.mauritius-year-1.yaml
```

Chain variants on the same ARC cluster. On multi-cluster ARC submissions, pass `-M arc` explicitly so dependencies are not lost across clusters:

```bash
JOB1_RAW=$(sbatch -M arc --parsable ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 configs/scenarios/config.mauritius-year-1.yaml)
JOB1=${JOB1_RAW%%;*}

JOB2_RAW=$(sbatch -M arc --dependency=afterany:$JOB1 --parsable ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-co2-zero-dea30 configs/scenarios/config.mauritius-year-1-co2-zero-dea30.yaml)
JOB2=${JOB2_RAW%%;*}

sbatch -M arc --dependency=afterany:$JOB2 ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-h2-dea30 configs/scenarios/config.mauritius-year-1-h2-dea30.yaml
```

## Spatial Resolution

Default solve configs use `clusters: ["12flex"]`. The profile build and cutout are not the same as network clustering:

- The ERA5/atlite cutout is configured with `dx: 0.1`, `dy: 0.1` degrees for Mauritius.
- Renewable profiles are built against unclustered onshore/offshore bus regions under `resources/mauritius-year-1/renewable_profiles/`.
- `cluster_network` later aggregates the electrical network to the requested `clusters` value and writes outputs such as `elec_s_12flex...`.

Do not use `clusters: [140]` as the default for Mauritius. It is likely more spatial detail than the island size, ERA5 grid, OSM network quality, and demand data can justify, and it may exceed the number of available model buses. Use 12flex as the first resolved run, then compare against 1, 6, and 24 if the OSM network supports it.

## Analysis Flow

Use the notebooks in this order:

1. `notebooks/00_cost_inputs_exploration.ipynb`
2. `notebooks/01_run_analysis.ipynb`
3. `notebooks/02_resolution_analysis.ipynb`
4. `notebooks/03_storage_soc_comparison.ipynb`

Default network path in the notebooks is `../results/mauritius-year-1/networks`.

Mauritius-specific analysis TODOs:

- Validate demand level and hourly shape against Mauritius sources.
- Build or curate a custom existing-powerplant file if powerplantmatching misses local units.
- Confirm treatment of bagasse/biomass, coal, oil, and fuel-price assumptions.
- Decide whether offshore wind should remain a candidate technology.
- Replace old Europe comparison annotations with Mauritius policy and emissions benchmarks.
- Add result checks for unserved energy/load shedding before interpreting costs.

## H2 And NH3 Extension Notes

The green-auklet H2/NH3 code was copied intact. Key locations:

- `pypsa-earth/scripts/add_extra_components.py`
- `pypsa-earth/scripts/add_electricity.py`
- `pypsa-earth/data/costs_dea2030.csv`
- `references/tech_config_ammonia_plant_2030_dea.yaml`

Scenario switches:

- H2: add `H2` to `electricity.extendable_carriers.Store` and `CCGT H2`, `H2 pipeline` to `Link`.
- NH3: add `NH3` to stores and `CCGT NH3`, `NH3 pipeline` to links. NH3 depends on H2 buses.

Keep H2/NH3 runs as comparison cases until the standard-tech Mauritius baseline is validated.

## Git Hygiene

- `results/`, `logs/`, local environments, cutouts, resources, and downloaded data stay ignored.
- Some PyPSA-Earth source data files are intentionally tracked despite broad upstream ignore rules; use explicit `git add -f` when creating the initial repository or adding curated data files.
- Do not commit ARC outputs, ERA5 cutouts, generated networks, or `.snakemake/`.

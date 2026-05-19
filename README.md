# PyPSA-Earth Mauritius Kestrel

Working PyPSA-Earth fork for modelling the Mauritius electricity system. The repo is seeded from `pypsa-earth-green-auklet` so it keeps the local setup scripts, Oxford ARC workflow, analysis notebooks, DEA 2030 cost files, and the hydrogen/ammonia extension code, but the active scenario set is Mauritius-first.

## Focus

- Country scope: Mauritius (`MU`)
- Initial model: up-to-12-node electricity system (`mauritius-year-1`)
- First priority: existing and standard electricity technologies
- Extension cases: hydrogen and ammonia are available but kept out of the default run
- Solver: Gurobi by default, with the upstream PyPSA-Earth solver configuration retained

## Repository Layout

```text
pypsa-earth-mauritius-kestrel/
├── pypsa-earth/                 # PyPSA-Earth model code and Mauritius configs
├── arc/                         # Oxford ARC setup and SLURM job scripts
├── notebooks/                   # Analysis notebooks copied from green-auklet flow
├── references/                  # DEA and fuel cost reference inputs
├── results/                     # Gitignored run outputs, kept with .gitkeep
├── local_setup.sh               # Local Python environment helper
└── DEVELOPMENT_NOTES.md         # Operating notes for future work
```

## Scenario Configs

Active configs live in `pypsa-earth/configs/scenarios/`:

| Config | Purpose |
| --- | --- |
| `config.mauritius-year-1-profiles.yaml` | Build the annual cutout and renewable profiles |
| `config.mauritius-year-1-stage.yaml` | Refresh Mauritius source inputs and cutout |
| `config.mauritius-year-1.yaml` | Baseline annual electricity run, standard techs only |
| `config.mauritius-week-1.yaml` | First-week smoke test using annual profiles |
| `config.mauritius-year-1-co2-zero-dea30.yaml` | Zero-CO2 standard-tech run with DEA 2030 costs |
| `config.mauritius-year-1-h2-dea30.yaml` | Zero-CO2 run with H2 storage and H2-to-power |
| `config.mauritius-year-1-nh3-dea30.yaml` | Zero-CO2 run with H2 and NH3 optionality |

All solve configs share `run.name: mauritius-year-1` so they reuse the same annual resources and renewable profiles. Do not run several solve jobs with the same `run.name` concurrently; the shared Snakemake lock and `_ec.nc` intermediates can collide.

## Local Setup

```bash
./local_setup.sh
source .venv/bin/activate
```

The setup script registers a Jupyter kernel named `pypsa-earth-mauritius-kestrel`
with display name `Python (PyPSA-Earth Mauritius)`.

Dry-run the baseline after setup:

```bash
cd pypsa-earth
snakemake --configfile configs/scenarios/config.mauritius-year-1.yaml --cores 4 --dry-run
```

The full workflow needs ERA5/CDS access when the cutout is not already present. Build profiles before solving:

```bash
cd pypsa-earth
snakemake --cores 4 \
  resources/mauritius-year-1/renewable_profiles/profile_solar.nc \
  --configfile configs/scenarios/config.mauritius-year-1-profiles.yaml
```

Then run the baseline solve:

```bash
snakemake --cores 4 \
  results/mauritius-year-1/networks/elec_s_12flex_ec_lcopt_3h.nc \
  --configfile configs/scenarios/config.mauritius-year-1.yaml
```

## ARC Workflow

Initial setup on ARC:

```bash
ssh <user>@arc-login.arc.ox.ac.uk
cd /data/<group>/<user>
git clone https://github.com/cpalazzi/pypsa-earth-mauritius-kestrel.git
cd pypsa-earth-mauritius-kestrel
bash arc/arc_initial_setup.sh
```

Build profiles, then solve:

```bash
cd /data/<group>/<user>/pypsa-earth-mauritius-kestrel/pypsa-earth

sbatch ../arc/jobs/01_build_profiles.sh \
  mauritius-year-1-profiles \
  configs/scenarios/config.mauritius-year-1-profiles.yaml

sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 \
  configs/scenarios/config.mauritius-year-1.yaml
```

Run extension cases after the baseline:

```bash
sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-h2-dea30 \
  configs/scenarios/config.mauritius-year-1-h2-dea30.yaml

sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-nh3-dea30 \
  configs/scenarios/config.mauritius-year-1-nh3-dea30.yaml
```

Use SLURM dependencies to chain variants that share `run.name`:

```bash
JOB1=$(sbatch --parsable ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 configs/scenarios/config.mauritius-year-1.yaml)

sbatch --dependency=afterany:${JOB1%%;*} ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-h2-dea30 configs/scenarios/config.mauritius-year-1-h2-dea30.yaml
```

## Analysis Flow

The notebooks in `notebooks/` keep the analysis structure from green-auklet and now point at `results/mauritius-year-1/networks` by default. The expected first pass is:

1. `00_cost_inputs_exploration.ipynb`
2. `01_run_analysis.ipynb`
3. `02_resolution_analysis.ipynb`
4. `03_storage_soc_comparison.ipynb`

The notebooks are intended to evolve with Mauritius-specific validation data, especially existing plant capacities, fuel prices, demand calibration, and policy targets.

## Cost And Extension Notes

`pypsa-earth/data/costs_dea2030.csv` and the reference spreadsheets in `references/` are copied from green-auklet. The H2/NH3 extension support is retained in:

- `pypsa-earth/scripts/add_extra_components.py`
- `pypsa-earth/scripts/add_electricity.py`
- `pypsa-earth/config.default.yaml`
- DEA and ammonia reference files under `references/`

Use the standard-tech baseline and zero-CO2 standard-tech run before interpreting H2 or NH3 cases.

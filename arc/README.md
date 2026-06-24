# ARC Cluster Scripts

Scripts for running the Mauritius PyPSA-Earth workflow on Oxford ARC.
These are technical instructions for the person running large jobs on the
university computing cluster; collaborators reviewing model assumptions do not
need to use them.

## Scripts

- `arc_initial_setup.sh`: one-time clone, directory, license, and environment setup.
- `build-pypsa-earth-env`: SLURM job to build the conda environment.
- `arc_check_run_inputs.sh`: checks whether the required renewable weather
  profiles already exist.
- `jobs/01_build_profiles.sh`: builds the wind and solar time series from
  weather data.
- `jobs/02_build_networks_and_solve_power.sh`: builds and solves electricity networks.

## Basic Run

From the repo checkout on ARC:

```bash
cd /data/<group>/<user>/pypsa-earth-mauritius-kestrel/pypsa-earth

sbatch ../arc/jobs/01_build_profiles.sh \
  mauritius-year-1-profiles \
  configs/scenarios/config.mauritius-year-1-profiles.yaml

../arc/arc_check_run_inputs.sh configs/scenarios/config.mauritius-year-1.yaml

sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 \
  configs/scenarios/config.mauritius-year-1.yaml
```

## Additional Comparison Runs

Run these only after the main wind and solar profile build succeeds:

```bash
sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-co2-zero-dea30 \
  configs/scenarios/config.mauritius-year-1-co2-zero-dea30.yaml

sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-h2-dea30 \
  configs/scenarios/config.mauritius-year-1-h2-dea30.yaml

sbatch ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-nh3-dea30 \
  configs/scenarios/config.mauritius-year-1-nh3-dea30.yaml
```

When runs share `run.name: mauritius-year-1`, submit them one after another
instead of at the same time:

```bash
JOB1_RAW=$(sbatch --parsable ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1 configs/scenarios/config.mauritius-year-1.yaml)
JOB1=${JOB1_RAW%%;*}

sbatch --dependency=afterany:$JOB1 ../arc/jobs/02_build_networks_and_solve_power.sh \
  mauritius-year-1-h2-dea30 configs/scenarios/config.mauritius-year-1-h2-dea30.yaml
```

## SSH Pattern

Use non-interactive SSH with one quoted remote command:

```bash
ssh <user>@arc-login.arc.ox.ac.uk 'cd /data/<group>/<user>/pypsa-earth-mauritius-kestrel/pypsa-earth && <command>'
```

Examples:

```bash
ssh <user>@arc-login.arc.ox.ac.uk 'squeue --clusters=all -u <user>'

ssh <user>@arc-login.arc.ox.ac.uk 'cd /data/<group>/<user>/pypsa-earth-mauritius-kestrel/pypsa-earth && ../arc/arc_check_run_inputs.sh configs/scenarios/config.mauritius-year-1.yaml'
```

## Monitoring

```bash
squeue --clusters=all -u <user>
tail -f logs/snakemake-*-build-profiles.log
tail -f logs/snakemake-*-solve-power.log
sacct -j <jobid> --format=JobID,JobName,State,Elapsed,MaxRSS,NodeList,ExitCode
```

## Download Results

```bash
rsync -av --progress <user>@arc-login.arc.ox.ac.uk:/data/<group>/<user>/pypsa-earth-mauritius-kestrel/pypsa-earth/results/mauritius-year-1/ pypsa-earth/results/mauritius-year-1/
```

## Troubleshooting

Unlock a failed Snakemake run:

```bash
cd pypsa-earth
snakemake --unlock
```

Check Gurobi license resolution:

```bash
echo "$GRB_LICENSE_FILE"
```

If profile preflight fails, rebuild profiles with:

```bash
sbatch ../arc/jobs/01_build_profiles.sh \
  mauritius-year-1-profiles \
  configs/scenarios/config.mauritius-year-1-profiles.yaml
```

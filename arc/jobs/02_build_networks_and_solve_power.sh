#!/bin/bash
#SBATCH --job-name=pypsa-earth-solve-power
#SBATCH --partition=short
#SBATCH --clusters=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=08:00:00
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=carlo.palazzi@eng.ox.ac.uk

if [[ $# -lt 2 ]]; then
  echo "Usage: sbatch ../arc/jobs/02_build_networks_and_solve_power.sh <run-label> <configfile> [configfile ...]" >&2
  echo "Example: sbatch ../arc/jobs/02_build_networks_and_solve_power.sh mauritius-year-1 configs/scenarios/config.mauritius-year-1.yaml" >&2
  exit 2
fi

if [ -f /etc/profile ]; then
  source /etc/profile
fi
if [ -f /etc/profile.d/modules.sh ]; then
  source /etc/profile.d/modules.sh
fi
if [ -f /etc/profile.d/lmod.sh ]; then
  source /etc/profile.d/lmod.sh
fi
if ! command -v module >/dev/null 2>&1; then
  source /usr/share/lmod/lmod/init/bash
fi

set -euo pipefail

SCENARIO="$1"
shift 1
CONFIG_FILES=("$@")
CONFIG_ARGS=()
for cfg in "${CONFIG_FILES[@]}"; do
  CONFIG_ARGS+=("--configfile" "$cfg")
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WORKDIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WORKDIR=${ARC_WORKDIR:-${SLURM_SUBMIT_DIR:-$DEFAULT_WORKDIR}}

if [[ ! -f "$WORKDIR/Snakefile" ]]; then
  # Try pypsa-earth subdirectory (common when submitting from repo root)
  if [[ -f "$WORKDIR/pypsa-earth/Snakefile" ]]; then
    echo "WARN: No Snakefile in WORKDIR '$WORKDIR'; falling back to '$WORKDIR/pypsa-earth'" >&2
    WORKDIR="$WORKDIR/pypsa-earth"
    # Config paths given relative to the repository root need the prefix stripped
    NEW_CONFIGS=()
    for cfg in "${CONFIG_FILES[@]}"; do
      NEW_CONFIGS+=("${cfg#pypsa-earth/}")
    done
    CONFIG_FILES=("${NEW_CONFIGS[@]}")
    CONFIG_ARGS=()
    for cfg in "${CONFIG_FILES[@]}"; do
      CONFIG_ARGS+=("--configfile" "$cfg")
    done
  elif [[ -f "$DEFAULT_WORKDIR/Snakefile" ]]; then
    echo "WARN: No Snakefile in WORKDIR '$WORKDIR'; falling back to '$DEFAULT_WORKDIR'" >&2
    WORKDIR="$DEFAULT_WORKDIR"
  fi
fi

CHECK_SCRIPT_CANDIDATES=(
  "$WORKDIR/../arc/arc_check_run_inputs.sh"
  "$WORKDIR/arc/arc_check_run_inputs.sh"
  "$SLURM_SUBMIT_DIR/../arc/arc_check_run_inputs.sh"
  "$SLURM_SUBMIT_DIR/arc/arc_check_run_inputs.sh"
  "$SCRIPT_DIR/../arc_check_run_inputs.sh"
)

CHECK_SCRIPT=""
for candidate in "${CHECK_SCRIPT_CANDIDATES[@]}"; do
  if [[ -n "${candidate}" && -x "${candidate}" ]]; then
    CHECK_SCRIPT="$candidate"
    break
  fi
done

if [[ -z "$CHECK_SCRIPT" ]]; then
  echo "Required profile preflight checker not found/executable." >&2
  echo "Checked:" >&2
  for candidate in "${CHECK_SCRIPT_CANDIDATES[@]}"; do
    echo "  $candidate" >&2
  done
  exit 2
fi

# Change to WORKDIR early so CHECK_SCRIPT and config paths resolve correctly
cd "$WORKDIR"

# Fail fast if annual profiles are missing for this config.
"$CHECK_SCRIPT" "${CONFIG_FILES[0]}"

# Force rebuild of add_extra_components intermediate so each scenario gets the
# correct extendable_carriers (H2 vs no-H2).  Also remove stale solved results
# so Snakemake doesn't skip the build.  Profiles and upstream intermediates are
# unaffected and fully reused.
read -r RUN_NAME OPTS_CSV < <(python3 -c "
import yaml, sys
for cfg in sys.argv[1:]:
    with open(cfg) as f:
        d = yaml.safe_load(f)
    rn = (d.get('run') or {}).get('name', '')
    sc = d.get('scenario') or {}
    opts = sc.get('opts', [])
    ll = sc.get('ll', ['copt'])
    clusters = sc.get('clusters', [140])
    # Build opt tokens that appear in result filenames
    tokens = []
    for o in opts:
        for l in ll:
            for c in clusters:
                tokens.append(f'l{l}_{o}')
    print(rn, ','.join(tokens))
    sys.exit(0)
print(' ')
" "${CONFIG_FILES[@]}" 2>/dev/null) || true

if [[ -n "$RUN_NAME" ]]; then
  # Remove _ec.nc intermediates (add_extra_components output)
  EC_GLOB="networks/${RUN_NAME}/elec_s*_ec.nc"
  if ls $EC_GLOB 1>/dev/null 2>&1; then
    echo "Removing stale _ec.nc intermediates to force rebuild with current config:"
    ls -lh $EC_GLOB
    rm -f $EC_GLOB
  fi

  # Remove _ec_*.nc intermediates (prepare_network outputs) so they are also rebuilt
  EC_PREP_GLOB="networks/${RUN_NAME}/elec_s*_ec_*.nc"
  if ls $EC_PREP_GLOB 1>/dev/null 2>&1; then
    echo "Removing stale prepare_network intermediates to force rebuild:"
    ls -lh $EC_PREP_GLOB
    rm -f $EC_PREP_GLOB
  fi

  # Remove stale solved result networks so Snakemake doesn't skip the job
  if [[ -n "$OPTS_CSV" ]]; then
    IFS=',' read -ra OPT_TOKENS <<< "$OPTS_CSV"
    for token in "${OPT_TOKENS[@]}"; do
      RESULT_GLOB="results/${RUN_NAME}/networks/elec_s*_ec_${token}.nc"
      if ls $RESULT_GLOB 1>/dev/null 2>&1; then
        echo "Removing stale result to force re-solve:"
        ls -lh $RESULT_GLOB
        rm -f $RESULT_GLOB
      fi
    done
  fi
fi

ANACONDA_MODULE=${ARC_ANACONDA_MODULE:-"Anaconda3/2024.06-1"}
module load "$ANACONDA_MODULE"

PYPSA_ENV=${ARC_PYPSA_ENV:-"/data/engs-df-green-ammonia/engs2523/envs/pypsa-earth-env"}

export PATH="$PYPSA_ENV/bin:$PATH"
SNAKEMAKE="$PYPSA_ENV/bin/snakemake"

export PYPSA_SOLVER_NAME=${PYPSA_SOLVER_NAME:-gurobi}
export LINOPY_SOLVER=${LINOPY_SOLVER:-gurobi}

# Use the ARC institutional token-server license (USELIMIT=4096) by pointing
# GRB_LICENSE_FILE directly at the known path — no `module load Gurobi` needed
# (that module ships Python 3.10 gurobipy which segfaults under Python 3.11).
# Fall back to the personal WLS license only if the system file is absent.
ARC_SYSTEM_GRB_LIC="/apps/system/easybuild/software/Gurobi/10.0.3-GCCcore-12.2.0/gurobi.lic"
ARC_LICENSE_DIR="${ARC_LICENSE_DIR:-/data/engs-df-green-ammonia/engs2523/licenses}"
if [[ -z "${GRB_LICENSE_FILE:-}" ]]; then
  if [[ -f "$ARC_SYSTEM_GRB_LIC" ]]; then
    export GRB_LICENSE_FILE="$ARC_SYSTEM_GRB_LIC"
  elif [[ -f "$ARC_LICENSE_DIR/gurobi.lic" ]]; then
    export GRB_LICENSE_FILE="$ARC_LICENSE_DIR/gurobi.lic"
  fi
fi
echo "Gurobi license: ${GRB_LICENSE_FILE:-(none set)}"

export PROJ_LIB=${PROJ_LIB:-"$PYPSA_ENV/share/proj"}
export PROJ_DATA=${PROJ_DATA:-"$PYPSA_ENV/share/proj"}
RERUN_TRIGGERS=${ARC_SNAKE_RERUN_TRIGGERS:-mtime}

DRYRUN_LOG=$(mktemp)
if ! "$SNAKEMAKE" \
  -n \
  solve_all_networks \
  --rerun-triggers "${RERUN_TRIGGERS}" \
  "${CONFIG_ARGS[@]}" >"$DRYRUN_LOG" 2>&1; then
  echo "ERROR: Dry-run for power solve failed. See output below:" >&2
  cat "$DRYRUN_LOG" >&2
  rm -f "$DRYRUN_LOG"
  exit 2
fi

if grep -Eq '^rule build_renewable_profiles:' "$DRYRUN_LOG"; then
  echo "WARN: Dry-run includes build_renewable_profiles; continuing because prerequisite files were validated." >&2
  echo "WARN: Using --rerun-triggers ${RERUN_TRIGGERS} to avoid metadata-only reruns where possible." >&2
fi
rm -f "$DRYRUN_LOG"

mkdir -p logs
export PYTHONPATH="$WORKDIR${PYTHONPATH:+:$PYTHONPATH}"

LOGFILE="logs/snakemake-${SCENARIO}-$(date +%Y%m%d-%H%M%S)-solve-power.log"
echo "Snakemake log: $LOGFILE"

MEM_MB=${SLURM_MEM_PER_NODE:-256000}
CPUS=${SLURM_CPUS_PER_TASK:-48}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$CPUS}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-$CPUS}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-$CPUS}
export GRB_THREADS=${GRB_THREADS:-$CPUS}
LATENCY_WAIT=${ARC_SNAKE_LATENCY_WAIT:-60}

"$SNAKEMAKE" \
  solve_all_networks \
  --rerun-triggers "${RERUN_TRIGGERS}" \
  "${CONFIG_ARGS[@]}" \
  -j "${CPUS}" \
  --resources mem_mb="${MEM_MB}" \
  --latency-wait "${LATENCY_WAIT}" \
  --keep-going --rerun-incomplete --printshellcmds \
  --stats "logs/snakemake-${SCENARIO}-solve-power.stats.json" 2>&1 | tee -a "$LOGFILE"

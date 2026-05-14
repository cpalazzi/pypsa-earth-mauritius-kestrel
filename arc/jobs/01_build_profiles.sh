#!/bin/bash
#SBATCH --job-name=pypsa-earth-build-profiles
#SBATCH --partition=short
#SBATCH --clusters=all
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=256G
#SBATCH --time=08:00:00
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=carlo.palazzi@eng.ox.ac.uk

if [[ $# -lt 2 ]]; then
  echo "Usage: sbatch ../arc/jobs/01_build_profiles.sh <run-label> <configfile> [configfile ...]" >&2
  echo "Example: sbatch ../arc/jobs/01_build_profiles.sh mauritius-year-1-profiles configs/scenarios/config.mauritius-year-1-profiles.yaml" >&2
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WORKDIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WORKDIR=${ARC_WORKDIR:-${SLURM_SUBMIT_DIR:-$DEFAULT_WORKDIR}}
cd "$WORKDIR"
mkdir -p logs
export PYTHONPATH="$WORKDIR${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN=${PYTHON_BIN:-"$PYPSA_ENV/bin/python"}

mapfile -t PROFILE_TARGETS < <("$PYTHON_BIN" - "$WORKDIR" "${CONFIG_FILES[@]}" <<'PY'
import os
import sys

try:
    import yaml
except Exception as exc:
    print(f"Missing dependency for config parsing: {exc}", file=sys.stderr)
    sys.exit(2)

workdir = sys.argv[1]
config_files = sys.argv[2:]

if not config_files:
    sys.exit(2)

def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def deep_merge(base, override):
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

cfg = {}
for path in ("config.default.yaml", "config.yaml"):
    cfg = deep_merge(cfg, load_yaml(os.path.join(workdir, path)))

for cfg_file in config_files:
    cfg_path = cfg_file if os.path.isabs(cfg_file) else os.path.join(workdir, cfg_file)
    cfg_override = load_yaml(cfg_path)
    base_config = (cfg_override.get("run", {}) or {}).get("base_config") or cfg_override.get("base_config")
    if base_config:
        base_path = base_config if os.path.isabs(base_config) else os.path.join(workdir, base_config)
        cfg = deep_merge(cfg, load_yaml(base_path))
    cfg = deep_merge(cfg, cfg_override)

renewable = cfg.get("renewable", {}) or {}
electricity = cfg.get("electricity", {}) or {}
carriers = set(electricity.get("renewable_carriers", []) or [])
techs = sorted([tech for tech in renewable.keys() if tech in carriers])
run_name = (cfg.get("run", {}) or {}).get("name", "")
rdir = f"{run_name}/" if run_name else ""

for tech in techs:
    print(f"resources/{rdir}renewable_profiles/profile_{tech}.nc")
PY
)

if [[ ${#PROFILE_TARGETS[@]} -eq 0 ]]; then
  echo "ERROR: No renewable profile targets detected from config files." >&2
  exit 2
fi

LOGFILE="logs/snakemake-${SCENARIO}-$(date +%Y%m%d-%H%M%S)-build-profiles.log"
echo "Snakemake log: $LOGFILE"

MEM_MB=${SLURM_MEM_PER_NODE:-256000}
CPUS=${SLURM_CPUS_PER_TASK:-48}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$CPUS}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-$CPUS}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-$CPUS}
export GRB_THREADS=${GRB_THREADS:-$CPUS}
LATENCY_WAIT=${ARC_SNAKE_LATENCY_WAIT:-60}

"$SNAKEMAKE" \
  "${PROFILE_TARGETS[@]}" \
  "${CONFIG_ARGS[@]}" \
  -j "${CPUS}" \
  --resources mem_mb="${MEM_MB}" \
  --latency-wait "${LATENCY_WAIT}" \
  --keep-going --rerun-incomplete --printshellcmds \
  --stats "logs/snakemake-${SCENARIO}-build-profiles.stats.json" 2>&1 | tee -a "$LOGFILE"

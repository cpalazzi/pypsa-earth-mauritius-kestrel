#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <configfile> <target-network> <cores>" >&2
  echo "Example: $(basename "$0") configs/scenarios/config.mauritius-week-1.yaml results/mauritius-year-1/networks/elec_s_1_ec_lcopt_3h-week01.nc 4" >&2
}

if [[ $# -lt 3 ]]; then
  usage
  exit 2
fi

CONFIG_FILE="$1"
TARGET_NETWORK="$2"
CORES="$3"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file not found: $CONFIG_FILE" >&2
  exit 2
fi

if [[ ! "$CORES" =~ ^[0-9]+$ ]]; then
  echo "Cores must be an integer: $CORES" >&2
  exit 2
fi

if ! command -v snakemake >/dev/null 2>&1; then
  echo "snakemake not found in PATH. Activate the PyPSA-Earth environment first." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKDIR"

PYTHON_BIN=${PYTHON_BIN:-python}
mapfile -t REQUIRED_PROFILES < <("$PYTHON_BIN" - "$WORKDIR" "$CONFIG_FILE" <<'PY'
import os
import sys

try:
    import yaml
except Exception as exc:
    print(f"Missing dependency for config parsing: {exc}", file=sys.stderr)
    sys.exit(2)

workdir = sys.argv[1]
config_file = sys.argv[2]

def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def deep_merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

cfg = {}
for path in ("config.default.yaml", "config.yaml"):
    cfg = deep_merge(cfg, load_yaml(os.path.join(workdir, path)))

cfg_override = load_yaml(config_file)
base_config = cfg_override.get("run", {}).get("base_config") or cfg_override.get("base_config")
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

if [[ ${#REQUIRED_PROFILES[@]} -eq 0 ]]; then
  echo "No renewable profiles requested by config; nothing to preflight." >&2
else
  missing=()
  for profile in "${REQUIRED_PROFILES[@]}"; do
    if [[ ! -f "$profile" ]]; then
      missing+=("$profile")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing renewable profiles (base-year reuse required):" >&2
    for profile in "${missing[@]}"; do
      echo "  $profile" >&2
    done
    exit 1
  fi
fi

ALLOWED_RULES=(
  base_network
  build_bus_regions
  build_demand_profiles
  add_electricity
  simplify_network
  cluster_network
  add_extra_components
  prepare_network
  solve_network
)

FORCE_RULES=(
  base_network
  build_bus_regions
)

snakemake -n \
  --cores "$CORES" \
  "$TARGET_NETWORK" \
  --configfile "$CONFIG_FILE" \
  --allowed-rules "${ALLOWED_RULES[@]}" \
  --forcerun "${FORCE_RULES[@]}"

snakemake \
  --cores "$CORES" \
  "$TARGET_NETWORK" \
  --configfile "$CONFIG_FILE" \
  --allowed-rules "${ALLOWED_RULES[@]}" \
  --forcerun "${FORCE_RULES[@]}"

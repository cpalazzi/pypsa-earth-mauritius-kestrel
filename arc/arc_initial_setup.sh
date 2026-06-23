#!/bin/bash
# ARC Initial Setup Script
# Run this on the ARC login node to set up the pypsa-earth environment
# 
# Usage: bash arc_initial_setup.sh

set -euo pipefail

echo "=================================================="
echo "PyPSA-Earth ARC Initial Setup"
echo "=================================================="
echo ""

# Configuration
USER=${USER:-engs2523}
GROUP=${ARC_GROUP:-engs-df-green-ammonia}
WORK_BASE="/data/${GROUP}/${USER}"
REPO_URL="${ARC_REPO_URL:-https://github.com/cpalazzi/pypsa-earth-mauritius-kestrel.git}"
REPO_DIR="${WORK_BASE}/pypsa-earth-mauritius-kestrel"
ENV_DIR="${WORK_BASE}/envs/pypsa-earth-env"
LICENSE_DIR="${WORK_BASE}/licenses"

echo "User: ${USER}"
echo "Work directory: ${WORK_BASE}"
echo "Repository directory: ${REPO_DIR}"
echo "Environment directory: ${ENV_DIR}"
echo ""

# Step 1: Clean old installations
echo "Step 1: Cleaning old installations..."
if [ -d "${WORK_BASE}/pypsa-earth" ]; then
    echo "  Removing old pypsa-earth directory..."
    rm -rf "${WORK_BASE}/pypsa-earth"
fi

if [ -d "${WORK_BASE}/pypsa-earth-runtools-crow" ]; then
    echo "  Removing old pypsa-earth-runtools-crow directory..."
    rm -rf "${WORK_BASE}/pypsa-earth-runtools-crow"
fi

if [ -d "${REPO_DIR}" ]; then
    echo "  Found existing repository at ${REPO_DIR}"
    read -p "  Do you want to remove it and clone fresh? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "${REPO_DIR}"
    else
        echo "  Keeping existing repository. Skipping clone."
    fi
fi

echo "  ✓ Cleanup complete"
echo ""

# Step 2: Clone repository
if [ ! -d "${REPO_DIR}" ]; then
    echo "Step 2: Cloning repository..."
    cd "${WORK_BASE}"
    echo "  Repository URL can be overridden with ARC_REPO_URL."
    echo "  Current URL: ${REPO_URL}"
    read -p "  Press Enter to continue or Ctrl+C to cancel and update the script..."
    
    git clone "${REPO_URL}" "$(basename ${REPO_DIR})"
    echo "  ✓ Repository cloned"
else
    echo "Step 2: Repository already exists, skipping clone"
    cd "${REPO_DIR}"
    git fetch --all
    git status
fi
echo ""

# Step 3: Setup directories
echo "Step 3: Setting up directories..."
mkdir -p "${ENV_DIR%/*}/logs"
mkdir -p "${LICENSE_DIR}"
mkdir -p "${REPO_DIR}/results"
mkdir -p "${REPO_DIR}/pypsa-earth/logs"
echo "  ✓ Directories created"
echo ""

# Step 4: Check Gurobi license
echo "Step 4: Checking Gurobi license..."
if [ -f "${LICENSE_DIR}/gurobi.lic" ]; then
    echo "  ✓ Gurobi license found at ${LICENSE_DIR}/gurobi.lic"
else
    echo "  ⚠ Gurobi license not found!"
    echo "  Please copy your gurobi.lic file to ${LICENSE_DIR}/gurobi.lic"
    echo "  You can do this with:"
    echo "    scp gurobi.lic ${USER}@arc-login.arc.ox.ac.uk:${LICENSE_DIR}/"
fi
echo ""

# Step 5: Submit environment build job
echo "Step 5: Building conda environment..."
echo "  This will submit a SLURM job to build the environment."
echo "  It will take 30-60 minutes to complete."
echo ""

read -p "  Do you want to submit the environment build job now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd "${REPO_DIR}/pypsa-earth"
    
    # Update the build script paths
    sed -i.bak "s|/data/engs-df-green-ammonia/engs2523|${WORK_BASE}|g" ../arc/build-pypsa-earth-env
    
    JOBID=$(sbatch ../arc/build-pypsa-earth-env | awk '{print $NF}')
    echo "  ✓ Job submitted: ${JOBID}"
    echo ""
    echo "  Monitor with:"
    echo "    squeue -j ${JOBID}"
    echo "    tail -f slurm-${JOBID}.out"
    echo ""
    echo "  When complete, verify with:"
    echo "    ${ENV_DIR}/bin/python --version"
    echo "    ${ENV_DIR}/bin/python -c 'import gurobipy; print(gurobipy.gurobi.version())'"
else
    echo "  Skipping environment build. You can run it later with:"
    echo "    cd ${REPO_DIR}/pypsa-earth"
    echo "    sbatch ../arc/build-pypsa-earth-env"
fi
echo ""

# Step 6: Summary
echo "=================================================="
echo "Setup Summary"
echo "=================================================="
echo ""
echo "Repository: ${REPO_DIR}"
echo "Environment: ${ENV_DIR}"
echo "Licenses: ${LICENSE_DIR}"
echo ""
echo "Next Steps:"
echo "1. Wait for environment build to complete (~30-60 min)"
echo "2. Verify Gurobi license is in place"
echo "3. Submit your first test run:"
echo "   cd ${REPO_DIR}/pypsa-earth"
echo "   sbatch ../arc/jobs/01_build_profiles.sh mauritius-year-1-profiles configs/scenarios/config.mauritius-year-1-profiles.yaml"
echo "   sbatch ../arc/jobs/02_build_networks_and_solve_power.sh mauritius-year-1 configs/scenarios/config.mauritius-year-1.yaml"
echo ""
echo "4. Monitor the job:"
echo "   squeue -u ${USER}"
echo "   tail -f logs/snakemake-*-solve-power.log"
echo ""
echo "5. Download results when complete:"
echo "   rsync -av ${USER}@arc-login.arc.ox.ac.uk:${REPO_DIR}/pypsa-earth/results/mauritius-year-1/ pypsa-earth/results/mauritius-year-1/"
echo ""
echo "=================================================="

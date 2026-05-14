#!/bin/bash
# Local development environment setup
# Run this on your local machine to set up pypsa-earth for development

set -euo pipefail

echo "=================================================="
echo "PyPSA-Earth Local Development Setup"
echo "=================================================="
echo ""

# Navigate to pypsa-earth directory
cd "$(dirname "$0")/pypsa-earth"

echo "Current directory: $(pwd)"
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "  ✓ Found Python 3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
    echo "  ✓ Found Python 3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo "  Found Python ${PYTHON_VERSION}"
    read -p "  Use this version? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Please install Python 3.10 or 3.11 and try again."
        exit 1
    fi
    PYTHON_CMD="python3"
else
    echo "  ✗ Python 3.10+ not found!"
    echo "  Please install Python 3.10 or 3.11 and try again."
    exit 1
fi
echo ""

# Check if .venv exists
if [ -d ".venv" ]; then
    echo "Virtual environment already exists."
    read -p "  Remove and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
    else
        echo "  Using existing virtual environment."
        echo "  Activate with: source pypsa-earth/.venv/bin/activate"
        exit 0
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
$PYTHON_CMD -m venv .venv
echo "  ✓ Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "  ✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel
echo "  ✓ pip upgraded"
echo ""

# Check if we should use conda environment.yaml
if [ -f "envs/environment.yaml" ]; then
    echo "Found environment.yaml"
    echo ""
    echo "Option 1: Install from conda environment.yaml (recommended)"
    echo "  This will install all dependencies from the conda environment file."
    echo "  Note: Some packages might not install via pip properly."
    echo ""
    echo "Option 2: Install core packages only (faster)"
    echo "  This will install only the essential packages."
    echo ""
    read -p "Choose option (1/2): " -n 1 -r
    echo
    
    if [[ $REPLY == "1" ]]; then
        echo "Installing from environment.yaml..."
        echo "  Note: This may take 10-20 minutes"
        
        # Extract package list from environment.yaml (excluding conda-only packages)
        # Install pypsa and core dependencies
        pip install "pypsa>=0.25.1,<=0.30.3"
        pip install "atlite>=0.4.1"
        pip install powerplantmatching
        pip install "earth-osm>=2.3.post1"
        pip install xlrd openpyxl seaborn
        pip install "snakemake<8"
        pip install memory_profiler
        pip install "ruamel.yaml<=0.17.26"
        pip install tables  # pytables
        pip install lxml
        pip install "numpy<2"
        pip install pandas
        pip install "geopandas>=1"
        pip install "fiona>=1.10"
        pip install "xarray>=2023.11.0,<=2025.01.2"
        pip install netcdf4
        pip install networkx
        pip install "scipy<1.16"
        pip install pydoe2
        pip install "shapely!=2.0.4"
        pip install matplotlib
        pip install reverse-geocode
        pip install country_converter
        pip install pyogrio
        pip install numba
        pip install py7zr
        pip install "tsam>=1.1.0"
        pip install fake-useragent
        # Pin chaospy/numpoly to avoid pulling numpy>=2 (linopy requires numpy<2)
        pip install "numpoly<1.3" "chaospy<4.3.21"
        pip install geopy
        pip install tqdm
        pip install pytz
        pip install ipykernel ipython jupyterlab
        pip install googledrivedownloader
        pip install cartopy
        pip install rasterio
        pip install rioxarray
        pip install geoviews
        pip install hvplot
        pip install contextily
        pip install rich
        pip install currencyconverter
        pip install dask
        
        echo "  ✓ Core packages installed"
    else
        echo "Installing core packages only..."
        pip install "pypsa>=0.25.1"
        pip install pandas geopandas xarray networkx
        pip install matplotlib seaborn
        pip install jupyterlab ipykernel
        pip install "snakemake<8"
        echo "  ✓ Core packages installed"
    fi
else
    echo "Installing core packages..."
    pip install pypsa pandas geopandas xarray networkx
    pip install matplotlib seaborn
    pip install jupyterlab ipykernel
    pip install snakemake
    echo "  ✓ Core packages installed"
fi
echo ""

# Install Gurobi
echo "Installing Gurobi..."
pip install gurobipy
echo "  ✓ Gurobi installed"
echo ""

# Check for Gurobi license
echo "Checking Gurobi license..."
python -c "import gurobipy; print(f'  Gurobi version: {gurobipy.gurobi.version()}')" 2>/dev/null || echo "  ⚠ Gurobi installed but license may not be configured"
echo ""
echo "  To set up Gurobi license:"
echo "    1. Get academic license from https://www.gurobi.com/academia/"
echo "    2. Run: grbgetkey <license-key>"
echo "    3. License will be saved to ~/gurobi.lic"
echo ""

# Create Jupyter kernel
echo "Installing Jupyter kernel..."
python -m ipykernel install --user --name pypsa-earth --display-name "Python (PyPSA-Earth)"
echo "  ✓ Jupyter kernel installed"
echo ""

# Summary
echo "=================================================="
echo "Setup Complete!"
echo "=================================================="
echo ""
echo "Virtual environment created at: $(pwd)/.venv"
echo ""
echo "To activate the environment:"
echo "  source pypsa-earth/.venv/bin/activate"
echo ""
echo "To deactivate:"
echo "  deactivate"
echo ""
echo "To run a test:"
echo "  cd pypsa-earth"
echo "  snakemake --configfile configs/scenarios/config.mauritius-year-1.yaml --cores 4 --dry-run"
echo ""
echo "To start Jupyter:"
echo "  jupyter lab"
echo ""
echo "Next steps:"
echo "  1. Ensure Gurobi license is configured"
echo "  2. Review configs/scenarios/config.mauritius-year-1.yaml"
echo "  3. Run a dry-run: snakemake --configfile configs/scenarios/config.mauritius-year-1.yaml --cores 4 --dry-run"
echo ""
echo "=================================================="

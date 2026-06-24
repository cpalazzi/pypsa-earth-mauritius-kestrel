# Mauritius Energy Network Model

This repository develops the Mauritius electricity component model for the
[`mu-star`](https://github.com/nismod/mu-star) infrastructure risk workflow.
Its primary purpose is to measure service interruption when existing energy
assets are damaged or unavailable.

The main model represents the power stations, transmission lines, substations
and electricity demand that already exist. It does not decide which new assets
Mauritius should build. For each hour, it works out which available power
stations can meet demand after one or more assets have been damaged or taken
out of service. Results include electricity demand that could not be supplied,
the share of demand served and operating cost.

## Choose The Modelling Track

### 1. Existing-system interruption model

Use this track to represent the existing Mauritius electricity system and test
what happens when assets are unavailable. This is the primary project work.
The code is under
`src/mu_star_energy/`; the guided review notebooks are under
`notebooks/asset_model/`.

```text
collaborator and open source data
  -> checked tables of power stations, substations, lines and demand
  -> a model of the existing electricity network
  -> a list of damaged or unavailable assets
  -> hourly electricity supply and unmet demand
```

The code uses this standard mu-star call:

```python
result = EnergyModel().simulate(network, disruptions)
```

Inputs are a prepared PyPSA model and a table listing unavailable power
stations, lines or substations. The model rejects settings that would allow it
to build extra generation, transmission or storage.

### 2. PyPSA-Earth reference track

Use this track to inspect a generic open-data PyPSA-Earth build, renewable
weather profiles, results for possible future systems, and how results change
when assumptions change. The included PyPSA-Earth code is under
`pypsa-earth/`; its analysis notebooks are under
`notebooks/pypsa_earth/`.

This track is useful for:

- an open-data estimate of which transmission substations are connected;
- ERA5 renewable profiles;
- generic GEGIS demand;
- comparison with a standard PyPSA-Earth run that chooses new capacity.

It is not the agreed record of existing CEB assets and does not feed the
interruption model automatically. Hydrogen, ammonia and future investment
cases are optional comparisons.

## Repository Layout

```text
├── src/mu_star_energy/          # Existing-system model code
├── config/energy.yaml           # Main model settings
├── config/damage_curves/        # How physical damage affects each asset type
├── workflow/                    # Automated data-preparation steps
├── notebooks/
│   ├── asset_model/             # Prepare and check the existing-system model
│   └── pypsa_earth/             # Explore open-data and future-system runs
├── data/
│   ├── 0-incoming/              # Received and downloaded source files
│   ├── 1-processed/             # Cleaned files used by the model
│   └── 2-out/                   # Model results
├── pypsa-earth/                 # Included PyPSA-Earth code and its outputs
├── arc/                         # PyPSA-Earth ARC scripts
└── DEVELOPMENT_NOTES.md
```

The root project has one ordered data tree. The numeric prefixes only make the
stages sort correctly in an IDE. PyPSA-Earth's own `data/`, `resources/`,
`networks/`, and `results/` stay inside the vendored `pypsa-earth/` directory.

## Plain-language Guide To Model Terms

- **Asset:** a physical item such as a power station, substation, line or
  transformer.
- **Bus:** PyPSA's name for a connection point. In the main electricity model,
  this is normally a substation.
- **Capacity:** the maximum power an asset can produce, carry or convert.
- **Carrier:** PyPSA's name for a fuel, technology or energy type, such as
  solar, oil, electricity, hydrogen or ammonia.
- **Dispatch:** the amount each power station produces in each model time step.
- **Line rating:** the maximum power a line can carry.
- **Service weight:** the share of total electricity demand assigned to a
  substation.
- **Snapshot:** one model time step, for example one hour or three hours.
- **Unserved energy / load shedding:** electricity demand that the available
  system could not supply.
- **Topology:** which substations and lines are connected to each other.

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

### 2. Prepare the source asset tables

```bash
.venv/bin/python -m mu_star_energy.cli prepare-assets
```

Equivalent Snakemake target:

```bash
.venv/bin/snakemake \
  --snakefile workflow/Snakefile \
  --cores 1 \
  data/1-processed/energy/collaborator/transmission_routes.parquet
```

These commands may overwrite generated files under `data/1-processed`.
Do not manually edit generated Parquet files.

### 3. Review and complete the model

Open the notebooks in this order:

1. `notebooks/asset_model/00_data_intake.ipynb`
2. `notebooks/asset_model/01_operational_network.ipynb`

The first checks which source records are available and creates a power-station
register template. The second displays the transmission routes and substations
as supplied. It does not infer which substations are connected.

`PowerGrid.shp` contains vector line geometry, not just an image. However, it
does not provide a complete electrical line register: most routes are unnamed,
and the attributes do not identify endpoint substations, circuit counts,
ratings or operating status. The separate `network_map_2025.png` is a reference
image and is not used to construct topology.

Add `existing_lines.csv` only when those electrical connections are available
from CEB records or another agreed source. The operational model does not
create connections from route proximity.

Information to prepare before interruption simulation:

- a unique ID, name and voltage for each substation;
- `existing_lines.csv`, with endpoint substations, voltage, length, circuit
  count and maximum power for each transmission line or transformer;
- `existing_generators.csv`, based on the generated register template, with
  `generator_id`, `bus_id`, `carrier`, `capacity_mw`, and `marginal_cost`
  populated and supported by CEB or other technical sources;
- a dated `demand_profile.csv` showing electricity demand over time;
- a reviewed share of total demand for each substation;
- approved damage curves and restoration assumptions.

In these files:

- `generator_id` is the unique power-station or generating-unit ID;
- `bus_id` is the substation to which the generator or demand is connected;
- `carrier` is the fuel or technology, such as hydro, solar or oil;
- `capacity_mw` is maximum electrical output in megawatts;
- `marginal_cost` is the estimated cost of producing one additional MWh;
- a line's `s_nom_mva` is the maximum apparent power it can carry.

`demand_profile.csv` may contain one system column named `demand_mw`, which is
shared between substations using `service_weights.csv`, or one complete column
per `bus_id`. Its first column must contain readable dates and times. A service
weight is simply the share of total demand assigned to a substation; all shares
must add to one.

### Current demand-profile support

The model code can already use demand that changes over time. The function
`build_operational_network(...)` accepts a table whose rows are model times and
whose values are demand in MW.

It supports two forms:

1. **One Mauritius-wide profile:** a `demand_mw` column. The same fixed demand
   shares from `service_weights.csv` are used at every time step to divide this
   total between substations.
2. **One profile per substation:** a column for every `bus_id`. These values are
   used directly and `service_weights.csv` is not used to divide the demand.

The current collaborator workbook provides monthly peak demand and annual
electricity use by customer group. It does not provide the hourly or
half-hourly series required for `demand_profile.csv`. The image
`Daily Profile.jpg` is also not read automatically.

The network builder reads the spacing between timestamps and applies the
correct duration to energy and cost totals. Regular half-hourly, hourly and
three-hourly profiles are therefore supported. Irregularly spaced timestamps
are rejected because their duration would be ambiguous.

The remaining implementation gap is file handling: the automated workflow
checks that `demand_profile.csv` exists, but it does not yet read that file,
build the final PyPSA network and run outage cases. At present, a Python script
or notebook must read the CSV into a pandas table, set its date/time column as
the index and pass it to `build_operational_network(...)`.

An hourly profile remains the simplest starting point, but it is not a
technical requirement.

### 4. Run outage cases

Once the required inputs are complete, build a PyPSA model that cannot add new
assets and call:

```python
result = EnergyModel().simulate(network, disruptions)
```

Write outage-case results beneath `data/2-out/energy/`.

## Choices To Review

The following settings are expected to change as better information becomes
available:

- the data root through `MU_STAR_DATA_ROOT`;
- the optional OSM and GridFinder data used to estimate each substation's share
  of demand;
- the calculation software, the assumed cost of unmet demand, the outage cases
  and the damage assumptions;
- the code that reads a source file when a collaborator supplies a different
  file format or set of columns. Record what changed and where the replacement
  data came from.

Keep these safeguards:

- do not modify received source files in `data/0-incoming`;
- do not present automatically inferred line connections, GridFinder routes or
  polygon sizes as confirmed CEB engineering data;
- do not change a unique asset ID without keeping a table that links the old ID
  to the new one;
- do not allow the interruption model to build extra generation, lines or
  storage;
- do not copy future-system results from PyPSA-Earth into the existing-system
  model without a documented review.

## How The Distribution Network Is Handled

The detailed low-voltage distribution network is unavailable. We therefore do
not treat it as part of the electrical network calculation:

- OSM distribution lines provide mapped evidence where available;
- GridFinder provides inferred network routes based on night lights and roads;
- combined line length is assigned to the nearest substation to estimate
  the share of demand served from each substation.

This is only a way to estimate where customers and demand may be located. It
does not provide reliable voltages, cable sizes, protection settings or
distribution power flows. GridFinder routes are estimates, not observed
infrastructure.

## PyPSA-Earth Comparisons

Start with `notebooks/pypsa_earth/README.md`. These notebooks are read-only
analysis tools unless a notebook explicitly states otherwise. Users are
expected to select or sync the required network/profile files and verify that
compared runs use the same main assumptions. File paths, technologies shown and
plot styles can be changed. When sharing results, state where the input data
came from, the year used for costs, the length of each model time step and the
assumptions that differ between runs.

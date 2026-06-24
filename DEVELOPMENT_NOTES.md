# Development Notes

## Project Role

This repository is the working Mauritius energy-model prototype for mu-star.
It should converge toward a package that can move into, or be called by,
`nismod/mu-star`.

The standard model interface is:

```python
EnergyModel.simulate(network, disruptions)
```

- `network`: existing assets, demand and settings for how they operate;
- `disruptions`: asset type, asset ID and the share that remains usable;
- output: electricity supplied, electricity not supplied and cost.

Do not let this model choose new power stations, lines or storage. Future
investment questions belong in the PyPSA-Earth comparison work or in a
separately defined adaptation study.

## Data Stages

The repository follows the mu-star convention:

```text
data/0-incoming  ->  data/1-processed  ->  data/2-out
```

These are the three stages of one project data tree. Do not add parallel
top-level `data_private`, `data_derived`, or `results` directories. All
contents are ignored. Only READMEs, processing code and configuration are
tracked. `MU_STAR_DATA_ROOT` can point these stages at the shared project data
location, including a locally synchronised OneDrive folder. The numeric
prefixes are ordering aids and do not change what each folder is for.

Current raw collaborator layout:

```text
data/0-incoming/energy/collaborator/
  power_demand/
    Power Demand.xlsx
    Daily Profile.jpg
  power_transmission/
    PowerGrid.*
  substation/
    Substation.*
    network_map_2025.png
  generation_source/
    GenSource1.*
    GenSource2.*
    Details about capacity and generation.url
```

Keep source files unchanged. Put any manual judgement in a cleaned register,
along with the source and a short explanation.

## Model Boundary

### Electrical model

PyPSA represents:

- each transmission substation as a model connection point (called a `Bus` in
  PyPSA);
- each transmission circuit or transformer as a connection with a fixed
  maximum power;
- existing power stations as fixed-capacity generators;
- demand assigned to each substation;
- an emergency high-cost supply option used only to measure electricity demand
  that cannot be served.

The model only chooses how existing power stations operate in each time step.
Every PyPSA setting that allows new capacity must remain false.

### Estimating the location of demand

The actual distribution system is not available. Use:

- OSM mapped distribution infrastructure where present;
- GridFinder estimated lines for areas where mapping is missing;
- population, customer or economic data when available.

These data help divide demand and customer impacts between substations. Do not
insert unconfirmed GridFinder lines into the electrical network calculation or
give them assumed capacities.

GridFinder estimates possible routes from night-time lights and roads. Keep a
`source` column so users can distinguish GridFinder estimates from OSM mapping
and CEB data.

## Notebook Separation

Primary asset-model notebooks:

1. `00_data_intake.ipynb` reads the collaborator files, lists the records found
   and shows missing power-station information.
2. `01_operational_network.ipynb` proposes connections between substations,
   estimates how demand is shared and lists missing inputs.

PyPSA-Earth reference notebooks:

1. `00_cost_inputs_exploration.ipynb` compares cost sources and years.
2. `01_run_analysis.ipynb` describes the results from one model run.
3. `02_resolution_analysis.ipynb` compares different time-step lengths.
4. `03_storage_soc_comparison.ipynb` compares selected model runs.
5. `04_profiles_analysis.ipynb` reviews demand, weather and the maximum
   renewable capacity allowed by land and sea assumptions.

Notebook outputs should be cleared before commit when they contain private data
or large embedded figures. The folder READMEs define prerequisites and which
settings users may change.

## Immediate Data Work

### Transmission and substations

- Reconcile the 18 point substations against names on the 2025 CEB map.
- Split mapped routes into individual lines between substations.
- Assign voltage, circuit count and maximum power.
- Add transformers where voltage conversion is represented.
- Document lines that are normally open or not operating.

### Existing generation

- Use the collaborator geometry for location.
- Create a register checked against CEB sources with unit/station name, fuel or
  technology, maximum output, dependable output, efficiency, ownership, status
  and dates.
- Assign every power station or generating unit to a transmission substation.
- Record whether capacities are station totals or individual units.
- Do not infer capacity from polygon area.

### Demand

- Preserve observed monthly peaks and annual sector totals from the workbook.
- Obtain hourly or half-hourly CEB demand if possible.
- Select and clearly state the year represented by the model.
- Divide demand between substations using OSM/GridFinder plus population or
  customer evidence.
- Keep customer-sector shares for later estimates of economic impact.

## Damage And Interruption Flow

The intended mu-star chain is:

```text
hazard intensity
  -> relationship between hazard and damage
  -> estimated share of the asset damaged
  -> usable share of the asset and repair time
  -> calculate supply using the remaining assets
  -> electricity demand not supplied by substation, time and sector
  -> economic impact, including the assumed cost of unmet demand
```

`config/damage_curves/` is intentionally empty pending approved curves. The
initial implementation converts `damage_fraction` to
`available_fraction = 1 - damage_fraction`; later work on repair time can
replace this simple relationship.

## PyPSA-Earth Reference Workflow

`pypsa-earth/` remains useful for comparison with:

- OSM transmission extraction;
- renewable weather profiles;
- generic demand comparison;
- open-data powerplant cross-checks.

The existing annual run is `mauritius-year-1`, with ARC instructions under
`arc/`. Its input files, model files and results stay under `pypsa-earth/`.
They provide a comparison and are not the primary existing-system model.

At the start of an ARC session, create the SSH control socket in a normal
terminal:

```bash
ssh -M -S ~/.ssh/arc-oxford-codex.sock -fnNT arc-oxford
```

## Environment

Use the repository environment:

```bash
source .venv/bin/activate
pip install -e .
```

The current environment uses Python 3.10 and PyPSA 0.30.3. Run:

```bash
.venv/bin/pytest
```

before committing model changes.

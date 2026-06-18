# Development Notes

## Project Role

This repository is the working Mauritius energy-model prototype for mu-star.
It should converge toward a package that can move into, or be called by,
`nismod/mu-star`.

The standard model interface is:

```python
EnergyModel.simulate(network, disruptions)
```

- `network`: fixed existing assets, demand and operational parameters;
- `disruptions`: component, asset identifier and available fraction;
- output: service and cost metrics, especially unserved energy.

Do not add greenfield capacity optimisation to this path. Investment scenarios
belong in the PyPSA-Earth reference track or a separately defined adaptation
analysis.

## Data Stages

The repository follows the mu-star convention:

```text
data/incoming  ->  data/processed  ->  data/out
```

All contents are ignored. Only READMEs, processing code and configuration are
tracked. `MU_STAR_DATA_ROOT` can point these stages at the shared project data
location, including a locally synchronised OneDrive folder.

Current raw collaborator layout:

```text
data/incoming/energy/collaborator/
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

Keep source files unchanged. Manual interpretation belongs in a processed
register with provenance columns.

## Model Boundary

### Electrical model

PyPSA represents:

- transmission substations as buses;
- transmission circuits/transformers as fixed-capacity branches;
- existing power stations as fixed-capacity generators;
- calibrated nodal demand;
- high-cost load-shedding generators to quantify unserved energy.

The model performs operational redispatch only. Every extendable-capacity flag
must remain false.

### Distribution proxy

The actual distribution system is not available. Use:

- OSM mapped distribution infrastructure where present;
- GridFinder inferred lines to fill spatial gaps;
- population, customer or economic data when available.

The proxy allocates demand and customer impacts to substations. Do not insert
unvalidated GridFinder lines into the PyPSA power-flow network or assign them
electrical ratings.

GridFinder predicts network routes from night-time lights and road-network
costs. Treat it as modelled evidence and retain a `source` field distinguishing
it from OSM and CEB data.

## Notebook Separation

Main notebooks:

1. `notebooks/asset_model/00_data_intake.ipynb`
2. `notebooks/asset_model/01_operational_network.ipynb`

Reference notebooks:

1. `notebooks/pypsa_earth/00_cost_inputs_exploration.ipynb`
2. `notebooks/pypsa_earth/01_run_analysis.ipynb`
3. `notebooks/pypsa_earth/02_resolution_analysis.ipynb`
4. `notebooks/pypsa_earth/03_storage_soc_comparison.ipynb`
5. `notebooks/pypsa_earth/04_profiles_analysis.ipynb`

Notebook outputs should be cleared before commit when they contain private data
or large embedded figures.

## Immediate Data Work

### Transmission and substations

- Reconcile the 18 point substations against names on the 2025 CEB map.
- Split the route geometry into individual branches between substations.
- Assign voltage, circuit count and thermal rating.
- Add transformers where voltage conversion is represented.
- Document normally-open or non-operational branches.

### Existing generation

- Use the collaborator geometry for location.
- Create a CEB-reconciled register with unit/station name, carrier, capacity,
  dependable capacity, efficiency, ownership, status and dates.
- Assign every generator to a transmission substation.
- Record whether capacities are station totals or individual units.
- Do not infer capacity from polygon area.

### Demand

- Preserve observed monthly peaks and annual sector totals from the workbook.
- Obtain hourly or half-hourly CEB demand if possible.
- Select a clearly dated baseline year.
- Allocate demand to substation service areas using OSM/GridFinder plus
  population/customer evidence.
- Preserve sector shares for later economic-impact attribution.

## Damage And Interruption Flow

The intended mu-star chain is:

```text
hazard intensity
  -> asset damage curve
  -> damage fraction
  -> availability and restoration duration
  -> PyPSA redispatch
  -> unserved energy by bus, time and sector
  -> value-of-lost-load / economic impact
```

`config/damage_curves/` is intentionally empty pending approved curves. The
initial implementation converts `damage_fraction` to
`available_fraction = 1 - damage_fraction`; restoration modelling can later
replace this simple relationship.

## PyPSA-Earth Reference Workflow

`pypsa-earth/` remains useful for:

- OSM transmission extraction;
- renewable weather profiles;
- generic demand comparison;
- open-data powerplant cross-checks.

The existing annual run is `mauritius-year-1`, with ARC instructions retained
under `arc/`. These results are validation/reference material, not the primary
mu-star model.

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

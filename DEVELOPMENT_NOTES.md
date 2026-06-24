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

## Current State

The repository now contains two related but separate models:

1. **Existing-system asset model:** collaborator and CEB data are used to
   describe the power stations, substations, transmission lines and demand that
   exist in Mauritius. This is the model intended for outage and damage
   analysis.
2. **PyPSA-Earth comparison model:** open data are used to build and optimise a
   possible power system. This model also produces useful hourly demand,
   weather and renewable-energy profiles.

The asset model does not currently import PyPSA-Earth files automatically.
PyPSA-Earth data are optional supporting inputs, not the default source of
existing assets or capacities.

Current asset-model preparation produces:

- 18 provisional substations;
- 19 proposed transmission lines, with maximum line power still missing;
- a power-station register template, with capacities, running costs and
  connected substations still to be completed;
- observed monthly peak demand and annual electricity use by customer group;
- equal demand shares between substations because no OSM/GridFinder
  distribution file has yet been added.

The Python network builder can use demand that changes over time, but the
automated workflow does not yet build and run the final model from
`demand_profile.csv`. Existing wind and solar generators also do not yet
receive weather-dependent availability profiles. Until that is added, every
non-damaged generator, including wind and solar, is available up to its full
installed capacity in every time step.

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

## Relationship With PyPSA-Earth Data

### Demand profile

The local PyPSA-Earth run contains:

```text
pypsa-earth/resources/mauritius-year-1/demand_profiles.csv
```

This file contains 8,760 hourly values across eight PyPSA-Earth regions. It was
generated from the GEGIS demand dataset using:

- SSP2-2.6 socioeconomic assumptions;
- a 2030 demand projection;
- 2013 weather/calendar patterns;
- a scale factor of 1;
- GDP and population to divide national demand between regions.

Before any asset-model calibration, the eight columns total about 4.55 TWh for
the year and have a combined peak of about 643 MW. These are modelled values,
not observed CEB demand. The columns use PyPSA-Earth region IDs (`0` to `7`),
not the asset model's substation IDs (`SUB_001`, etc.).

Possible use in the asset model:

1. add the eight columns to create one Mauritius-wide hourly shape;
2. calibrate that shape to agreed CEB annual demand and peak information;
3. divide the national profile between asset-model substations using reviewed
   demand shares.

This would be a temporary estimated profile, not observed CEB hourly demand.
The chosen weather/demand year, scaling target and method should be saved with
the processed file. One multiplier can match annual demand or peak demand, but
will not generally match both. Matching both may require a documented change
to the shape as well as scaling. Directly copying the eight PyPSA-Earth columns
into the asset model would be incorrect because the two models use different
locations.

Preferred source order:

1. observed CEB hourly or half-hourly demand;
2. another observed Mauritius system profile with a clear year and source;
3. the PyPSA-Earth hourly shape, scaled to CEB totals and clearly labelled as
   estimated.

### Wind and solar availability

The local PyPSA-Earth run also contains hourly 2013 weather-based availability
profiles generated from ERA5 weather data on a 0.1-degree grid:

```text
pypsa-earth/resources/mauritius-year-1/renewable_profiles/
  profile_solar.nc
  profile_onwind.nc
  profile_offwind-ac.nc
  profile_offwind-dc.nc
```

These profiles describe the share of installed capacity that weather allows at
each hour. They can be useful for existing wind and solar assets after each
asset has been matched to the nearest suitable profile region.

Only the hourly `profile` values should be used for the existing-system model.
The PyPSA-Earth `p_nom_max` and `potential` fields describe how much new
capacity could potentially be built; they must not replace CEB installed
capacity.

Current local profile limitations:

- solar and onshore wind contain usable hourly profiles;
- the AC offshore-wind profile is zero in this run;
- the DC offshore-wind profile has values but would only be relevant if an
  existing or explicitly studied offshore asset is included;
- the hydro profile contains no plants, so existing hydro needs CEB generation,
  water-flow information or another documented assumption.

### Other possible cross-checks

PyPSA-Earth can also help check OSM transmission mapping and open power-station
records. Differences should be reported for review; they should not
automatically overwrite collaborator or CEB records.

## Development Tasks

### Priority 1: complete a runnable existing-system model

- Confirm substation names, voltage levels and unique IDs.
- Review every proposed transmission connection against CEB maps and local
  knowledge.
- Add maximum power for lines and transformers.
- Complete `existing_generators.csv` with installed capacity, fuel or
  technology, running cost, efficiency, status and connected substation.
- Decide the model year and document whether each input represents that year.
- Replace equal demand shares with reviewed substation shares where evidence is
  available.

Completion check: the model builds without missing-input errors and can meet
normal demand without using the emergency unmet-demand option.

### Priority 2: integrate demand over time

- Add a command that reads `demand_profile.csv`, checks timestamps, units,
  missing values and time-step length, then reports annual demand and peak.
- Add a preparation option for observed CEB hourly or half-hourly data.
- Add an optional PyPSA-Earth fallback that:
  - reads the eight-region 2013 profile;
  - creates a national hourly shape;
  - chooses and documents whether annual demand, peak demand or both are
    calibration targets;
  - adjusts the shape explicitly if both annual and peak targets are matched;
  - records the source year and scaling method;
  - writes the standard asset-model `demand_profile.csv`.
- Decide whether one fixed substation share is adequate or whether demand
  shares should vary by hour or customer sector.
- Add checks comparing the processed profile with CEB monthly peaks, annual
  sector totals and any published load-factor information.

Suggested output:

```text
data/1-processed/energy/collaborator/
  demand_profile.csv
  demand_profile_metadata.json
```

### Priority 3: integrate generation availability over time

- Extend `build_operational_network(...)` to accept an optional table of
  availability values between zero and one for each generator and time step.
- Add a standard processed file, for example
  `generator_availability.csv`, using `generator_id` columns.
- Match each existing solar and wind generator to a PyPSA-Earth weather region
  using its coordinates and technology.
- Use PyPSA-Earth hourly `profile` values, but retain CEB installed capacity
  from `existing_generators.csv`.
- Add source and weather-year information for every assigned profile.
- Develop separate assumptions for:
  - hydro, preferably using CEB generation or water data;
  - thermal planned maintenance and forced outages;
  - storage operation, if existing storage is added.
- Check annual capacity factors and monthly generation against CEB reports.

Suggested outputs:

```text
data/1-processed/energy/collaborator/
  generator_availability.csv
  generator_profile_assignments.csv
  generator_profile_metadata.json
```

### Priority 4: connect preparation, model build and outage runs

- Add a command to build the final PyPSA network from cleaned buses, lines,
  generators, demand and optional generation profiles.
- Add a normal-operation run before applying damage.
- Add automated outage runs from a disruption table.
- Save the built network, summary results and unmet demand by substation and
  time under `data/2-out/energy/`.
- Replace the current Snakemake file-existence check with rules that prepare
  profiles, build the network, run the normal case and run outage cases.
- Add a third asset-model notebook that reviews demand, generation profiles and
  the normal-operation result without mixing it with data intake.

### Priority 5: validate the model

- Reconcile annual electricity demand, peak demand and sector totals.
- Compare annual generation by technology with CEB reports.
- Compare renewable capacity factors with reported generation and independent
  weather-based estimates.
- Check normal-operation line loading and investigate overloaded lines.
- Confirm that normal operation has no unmet demand except where deliberately
  allowed for testing.
- Test known outages or historical disruption events where evidence exists.
- Record uncertainty ranges for line limits, demand allocation, running costs
  and renewable profiles.

### Priority 6: damage, restoration and economic impact

- Agree hazard measures and damage relationships for each asset type.
- Add time-dependent restoration rather than one fixed available fraction.
- Represent common-cause events affecting several nearby assets.
- Report unmet demand by substation, time and customer sector.
- Connect customer-sector impacts to value-of-lost-load or wider economic
  impact methods, with assumptions visible.

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

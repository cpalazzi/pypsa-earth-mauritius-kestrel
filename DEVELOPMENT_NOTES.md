# Development notes

## Project role

This repository is the working Mauritius energy-model prototype for mu-star.
It should converge toward a package that can move into, or be called by,
`nismod/mu-star` as the `energy` component model.

The public model interface to keep stable is:

```python
EnergyModel().simulate(network, disruptions)
```

- `network`: a prepared PyPSA network for the supplied fixed-capacity system;
- `disruptions`: asset type, asset ID and the share that remains usable;
- output: `SimulationResult(metrics: dict, network)`, including electricity
  supplied, electricity not supplied and cost.

The model dispatches supplied assets only. New power stations, lines or storage
must appear in the input system before the run starts. Future investment
questions belong in the PyPSA-Earth comparison work or in a separately defined
adaptation study.

## Delivery to mu-star

Target delivery path:

```text
this repo: src/mu_star_energy  ->  nismod/mu-star: src/energy
```

The local mu-star checkout at `/Users/carlopalazzi/programming/mu-star` uses
`src/<model_name>/` packages and exposes the example
`src/transport/model.py::SampleModel.simulate(network, disruptions)` interface.
`EnergyModel.simulate(...)` already follows the same call shape. It currently
returns a `SimulationResult` so notebook users can inspect both metrics and the
solved network; if mu-star orchestration needs a plain metrics object, add a
thin adapter that returns `EnergyModel().simulate(...).metrics`.

Data-stage mapping for delivery:

```text
this repo data/0-incoming/energy   ->  mu-star incoming/energy
this repo data/1-processed/energy  ->  mu-star processed/energy
this repo data/2-out/energy        ->  mu-star out/energy
```

Keep the numbered stage names locally until the package is moved. They are
ordering aids, not a different data model.

Disruption-schema mapping:

- this package consumes `component`, `asset_id`, and `available_fraction`;
- current helper input is `component`, `asset_id`, and `damage_fraction`;
- mu-star damage outputs described in the delivery brief use `fraction` and
  `monetary`, so the energy adapter should map damage fraction to
  `available_fraction = 1 - fraction` and leave monetary impact for downstream
  economic analysis.

Delivery checklist:

- move or rename imports from `mu_star_energy` to `energy`, or keep a temporary
  compatibility shim during migration;
- add the energy dependencies to mu-star, probably behind an optional extra:
  `geopandas`, `networkx`, `pyarrow`, `pypsa>=0.30,<0.31`, `pyyaml`, and
  `shapely`;
- confirm the solver path for PyPSA/linopy, including HiGHS, in the mu-star
  environment;
- test under Python 3.12 before delivery. This package currently declares
  `requires-python = ">=3.10"` while mu-star declares `>=3.12`;
- keep `EnergyModel().simulate(network, disruptions)` stable and keep
  `assert_fixed_capacity(...)` in the run path.

Standalone run path:

1. install the package with `pip install -e .`;
2. run `python -m mu_star_energy.cli prepare-assets`;
3. review and complete `generators.csv`, `lines.csv`,
   `demand_profile.csv`, and `service_weights.csv` under
   `data/1-processed/energy/collaborator`;
4. build a PyPSA network with `build_operational_network(...)`;
5. call `EnergyModel().simulate(network, disruptions)`.

## Module map

- `intake.py`: validates collaborator source folders and writes cleaned
  substations, route geometry, generation layers, demand summaries and register
  templates.
- `network.py`: builds a fixed-capacity PyPSA network from reviewed buses,
  lines, generators, demand and service weights.
- `network_source.py`: builds saved `base` and `inferred` PyPSA network
  handoff files from named source paths.
- `model.py`: applies disruptions to a copied network, optimises supply and
  returns standard supply metrics.
- `damage.py`: converts asset damage fractions into usable asset fractions for
  the energy model.
- `distribution.py`: estimates substation demand shares from OSM/GridFinder
  line-length proxies without adding inferred feeders to the electrical
  network.
- `distribution_network.py`: builds the explicitly inferred
  GridFinder/OSM topology-only distribution graph and estimates downstream
  disconnection impacts.
- `paths.py`: centralises repository and data-stage paths, including
  `MU_STAR_DATA_ROOT`.
- `cli.py`: exposes the current `prepare-assets` and `run-interruptions`
  command-line entry points.
- `runner.py`: loads reviewed model inputs, runs baseline/outage simulations
  and writes metrics, network files and unmet-demand tables.

## Current state

The repository now contains two related but separate models:

1. **Interruption model:** collaborator and CEB data currently describe
   the power stations, substations, transmission lines and demand in Mauritius.
   This is the model intended for outage and damage analysis.
2. **PyPSA-Earth comparison model:** open data are used to build and optimise a
   possible power system. This model also produces useful hourly demand,
   weather and renewable-energy profiles.

The interruption model does not currently import PyPSA-Earth files automatically.
PyPSA-Earth data are optional supporting inputs, not the default source of
existing assets or capacities.

Current interruption-model preparation produces:

- 18 provisional substations;
- six vector transmission-route records;
- a power-station register template, with capacities, running costs and
  connected substations still to be completed;
- observed monthly peak demand and annual electricity use by customer group;
- equal demand shares between substations because no OSM/GridFinder
  distribution file has yet been added.

The Python network builder and CLI can use demand that changes over time.
`build-network` writes the saved PyPSA handoff; `run-interruptions` can load
that handoff with `--network` / `--network-source`, run a baseline case and run
an outage case from a disruption table. Existing wind and solar generators can
receive an optional availability profile during network build, but the
workflow does not yet create those profiles automatically from PyPSA-Earth
weather files. Without a supplied availability table, every non-damaged
generator is available up to its full installed capacity in every time step.
Every interruption run writes `demand_summary.csv` with system-level and
substation-level profile demand, annualized demand, peak demand and load
factor for validation.
`build-network inferred --allow-provisional-demand` currently writes a
structural inferred-network handoff at
`data/1-processed/energy/networks/inferred.nc` using the local PyPSA-Earth OSM
line extraction fallback when no cached GridFinder/OSM distribution file is
present. The reviewed `base` network is still blocked until `lines.csv`,
`generators.csv` and `demand_profile.csv` are supplied.

## Data stages

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

## Model boundary

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

Capacity conventions:

- existing generators use electrical output capacity in `MW_e`;
- generator marginal cost is per `MWh_e`, with LHV or HHV fuel assumptions
  recorded separately;
- AC lines and transformers use `s_nom` apparent-power ratings in MVA;
- bus voltage is in kV;
- explicit conversion technologies use input-side `Link.p_nom`, with output
  equal to input multiplied by efficiency.

PyPSA does not impose LHV or HHV. Record the basis used by each fuel-price and
efficiency source. The current builder supports AC lines only; add explicit
transformer-table support before representing substations with multiple voltage
levels.

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

For a distribution-network experiment, keep GridFinder routes out of the
reviewed baseline and label the alternative topology as inferred. Start with
graph connectivity and downstream demand disconnection. Distribution
power-flow cases require separate voltage-level buses and transformers, plus
named sensitivity sets for assumed feeder capacities and impedances.

## Notebook separation

Primary interruption-model notebooks:

1. `00-data-review/00_data_review.ipynb` reads the collaborator files, lists
   the records found, shows substation snap distances and identifies missing
   power-station information. It does not build a model.
2. `01-build-network/00_build_network.ipynb` displays the routes and snapped
   substations, estimates how demand is shared, lists missing model inputs and
   calls `build_network(source=...)` to write a saved PyPSA network handoff.
3. `02-interruption-analysis/00_interruption_analysis.ipynb` loads a saved
   `networks/<source>.nc` file and runs baseline/outage cases without
   rebuilding source-specific network inputs.

The line geometry does not identify the two endpoint substations for
each electrical circuit. The repository therefore does not convert mapped
routes into model connections. `lines.csv` will be the model input
once endpoint and engineering data are available from an agreed source.

The current `PowerGrid.shp` contains six route records, expanded into 27 line
parts. Only one record has a route name and voltage in its attributes. It has
no fields identifying `bus0`, `bus1`, circuit count, thermal rating or
operational status. `Substation.shp` contains 18 points, all labelled only
`Substation`. The map is therefore useful evidence, but it is not yet a
complete electrical network register.

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

## Relationship with PyPSA-Earth data

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

Before any interruption-model calibration, the eight columns total about 4.55 TWh for
the year and have a combined peak of about 643 MW. These are modelled values,
not observed CEB demand. The columns use PyPSA-Earth region IDs (`0` to `7`),
not the interruption model's substation IDs (`SUB_001`, etc.).

Possible use in the interruption model:

1. add the eight columns to create one Mauritius-wide hourly shape;
2. calibrate that shape to agreed CEB annual demand and peak information;
3. divide the national profile between interruption-model substations using reviewed
   demand shares.

This would be a temporary estimated profile, not observed CEB hourly demand.
The chosen weather/demand year, scaling target and method should be saved with
the processed file. One multiplier can match annual demand or peak demand, but
will not generally match both. Matching both may require a documented change
to the shape as well as scaling. Directly copying the eight PyPSA-Earth columns
into the interruption model would be incorrect because the two models use different
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

Only the hourly `profile` values should be used for the fixed-capacity
interruption model.
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

## Development tasks

### Priority 1: complete a runnable fixed-capacity interruption model

- Confirm substation names, voltage levels and unique IDs.
- Derive a geometric network from `PowerGrid.shp` without adding new routes:
  - snap every substation to the nearest mapped line;
  - retain each original coordinate and record the snap distance;
  - split mapped lines at snapped substations and genuine line intersections;
  - preserve the source route ID on every resulting segment.
- Show the snap-distance table prominently in the intake notebook. Most points
  move less than 75 m, while `SUB_014` moves about 301 m because the source map
  is coarse.
- Complete `lines.csv` from CEB records, identifying the endpoint
  substations for each line or transformer.
- Add voltage, circuit count and maximum power for lines and transformers.
- Complete `generators.csv` with installed capacity, fuel or
  technology, running cost, efficiency, status and connected substation.
- Decide the model year and document whether each input represents that year.
- Replace equal demand shares with reviewed substation shares where evidence is
  available.

Completion check: the model builds without missing-input errors and can meet
normal demand without using the emergency unmet-demand option.

### Priority 2: integrate demand over time

- The `run-interruptions` command now reads `demand_profile.csv`, checks
  timestamps, missing values and time-step length, uses it in baseline and
  outage runs, and writes a demand-summary report for annualized demand, peak
  and load factor.
- Add a preparation option for observed CEB hourly or half-hourly data.
- Add an optional PyPSA-Earth fallback that:
  - reads the eight-region 2013 profile;
  - creates a national hourly shape;
  - chooses and documents whether annual demand, peak demand or both are
    calibration targets;
  - adjusts the shape explicitly if both annual and peak targets are matched;
  - records the source year and scaling method;
  writes the standard interruption-model `demand_profile.csv`.
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

- `build_operational_network(...)` now accepts an optional table of
  availability values between zero and one for each generator and time step.
- Use `generator_availability.csv` as the standard processed file, with
  timestamp rows and `generator_id` columns.
- Match each existing solar and wind generator to a PyPSA-Earth weather region
  using its coordinates and technology.
- Use PyPSA-Earth hourly `profile` values, but retain CEB installed capacity
  from `generators.csv`.
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

- The `build-network` command builds the final PyPSA network from cleaned
  buses, lines, generators, demand and optional generation profiles.
- The `run-interruptions` command loads a saved network handoff with
  `--network` / `--network-source`, with CSV rebuilding retained only as a
  fallback.
- It runs normal operation before applying damage.
- It can run an outage case from a disruption table.
- It saves the built network, summary results and unmet demand by substation
  and time under `data/2-out/energy/`.
- Snakemake now has rules for baseline and disruption runs; remaining work is
  to add profile-preparation rules when observed demand or weather-derived
  generator profiles are available.
- Add a third interruption-model notebook that reviews demand, generation profiles and
  the normal-operation result without mixing it with data intake.

### Priority 4a: inferred distribution-network experiment

- `prepare-inferred-distribution --enable-inferred-distribution` builds a
  labelled topology-only graph from GridFinder and OSM distribution lines.
- `build-network inferred` now converts that graph style into a fixed-capacity
  PyPSA network handoff. The current local generated `inferred.nc` uses
  provisional one-snapshot peak demand and contains no reviewed physical
  generators, so smoke-test optimisation sheds all demand by design.
- The standalone graph command writes nodes and edges under
  `data/1-processed/energy/inferred_distribution/`; the saved-network builder
  writes its graph tables beside the handoff network under
  `data/1-processed/energy/networks/inferred_distribution/`.
- Stage A is connectivity only: remove failed substations or feeder edges and
  count proxy demand disconnected from every reviewed substation root.
- Stage B remains future work: distribution power flow needs transformer-table
  support, separate voltage-level buses and named sensitivity sets for feeder
  capacity and impedance.
- Keep these outputs out of `lines.csv` and out of the reviewed
  baseline unless a future review explicitly promotes specific assets.

### Priority 5: validate the model

- Unit tests now check that `EnergyModel().simulate(...)` returns a metrics
  dictionary with the expected mu-star supply metrics while preserving the
  solved network for inspection.
- Python 3.12 is available locally, but a temporary 3.12 dependency install did
  not complete during the current review because the PyPSA/geospatial wheel
  download stalled. Run the full test suite in a completed Python 3.12
  environment before moving the package into `nismod/mu-star`.
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

## Damage and interruption flow

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

## PyPSA-Earth reference workflow

`pypsa-earth/` remains useful for comparison with:

- OSM transmission extraction;
- renewable weather profiles;
- generic demand comparison;
- open-data powerplant cross-checks.

The existing annual run is `mauritius-year-1`, with ARC instructions under
`arc/`. Its input files, model files and results stay under `pypsa-earth/`.
They provide a comparison and are not the primary reviewed model.

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

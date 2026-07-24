# Development notes

## Project role

This repository is the working Mauritius energy-model prototype for mu-star.
It should converge toward a package that can move into, or be called by,
`nismod/mu-star` as the `energy` component model.

The public model interface to keep stable is:

```python
EnergyModel().simulate(network, disruptions)
```

- `network`: a prepared PyPSA network for the provided fixed-capacity system;
- `disruptions`: asset type, asset ID and the share that remains usable;
- output: `SimulationResult(metrics: dict, network)`, including electricity
  supplied, electricity not supplied and cost.

The model dispatches the provided assets only. New power stations, lines or storage
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
2. run `python -m mu_star_energy.cli prepare-assets` to generate cleaned source
   evidence and the human CSV schemas under `data/1-processed/energy/templates`;
3. review generated `generators.csv`, line-length and generation-capacity
   coverage validation, and the demand inputs under
   `data/1-processed/energy/provided`;
4. build and save `networks/base-mauritius/base-mauritius.nc`, then attach demand to that network;
5. call `EnergyModel().simulate(network, disruptions)`.

## Module map

- `intake.py`: validates provided source folders and writes cleaned
  substations, route geometry, generated `generators.csv`, service weights and
  demand summaries.
- `network.py`: builds a fixed-capacity PyPSA topology and attaches demand and
  service weights to a saved topology for a run.
- `network_source.py`: builds and saves the reviewed `base` plus the explicit
  `inferred-osm` and `inferred-data` PyPSA topology products.
- `nightlight_targets.py`: extracts VIIRS nightlight targets (high-pass filter
  and threshold) used to select the supported road subnetwork.
- `spatial_export.py`: writes deterministic node/edge GeoParquet views and a
  manifest bound to the canonical NetCDF checksum.
- `network_tables.py`: defines the human CSV schemas, writes source-specific
  review exports and performs advisory coverage validation.
- `model.py`: applies disruptions to a copied network, optimises supply and
  returns standard supply metrics.
- `damage.py`: converts asset damage fractions into usable asset fractions for
  the energy model.
- `distribution.py`: estimates substation demand shares from OSM/precomputed
  line-length proxies without adding inferred feeders to the electrical
  network.
- `distribution_network.py`: builds the explicitly inferred
  precomputed/OSM topology-only distribution graph and estimates downstream
  disconnection impacts.
- `paths.py`: centralises repository and data-stage paths, including
  `MU_STAR_DATA_ROOT`.
- `cli.py`: exposes the `prepare-assets`, `build-network`, `run-interruptions`
  and `prepare-inferred-distribution` command-line entry points.
- `runner.py`: loads a saved PyPSA network, attaches run-time demand, runs
  baseline/outage simulations and writes metrics and unmet-demand tables.

## Current state

The repository holds two separate models: the **interruption model** (provided
and CEB data describing Mauritius power stations, substations, lines and demand,
used for outage and damage analysis) and the **PyPSA-Earth comparison model**
(an open-data build for hourly demand, weather and renewable profiles). The
interruption model does not import PyPSA-Earth files automatically; those are
optional supporting inputs, not the default asset source.

Current interruption-model preparation produces:

- 18 provided substations, with their original and route-snapped coordinates
  retained;
- six vector transmission-route records;
- generated power-station records with geometry, nearest substations and CEB
  report capacity for clearly matched station names;
- observed monthly peak demand and annual electricity use by customer group;
- equal demand shares between substations because no OSM/precomputed
  distribution file has yet been added.

The Python network builder and CLI can use demand that changes over time.
`build-network` writes the saved topology-only PyPSA network; `run-interruptions`
loads that saved network with `--network` / `--network-source`, attaches demand,
runs a baseline case and runs an outage case from a disruption table. Existing
wind and solar generators can receive an optional availability profile during
the interruption run, but the workflow does not yet create those profiles
automatically from PyPSA-Earth weather files. Without a provided availability
table, every non-damaged generator is available up to its full installed
capacity in every time step.
Every interruption run writes `demand_summary.csv` with system-level and
substation-level profile demand, annualized demand, peak demand and load
factor for validation.
`build-network inferred-osm --region <query>` and `build-network
inferred-data --region <query>` run the same nightlight-driven road filter.
The first uses OSM substations, plants and generators as known
terminals; the second uses reviewed input substations and generator sites.
VIIRS nightlight targets retain the dense OSM road subnetwork within the
configured support distance, rather than reducing it to a least-cost tree. The
default `all` OSM extract is retained separately as a length-validation
envelope against CEB's reported 10,492.2 km. Existing outputs are not
overwritten without `--overwrite`. The `base` topology remains the only
reviewed operational topology.

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

Current raw provided layout:

```text
data/0-incoming/energy/provided/
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

#### Deferred: design voltage, line ratings and the 132 kV uprating scenario

Not needed yet — current priority is the `build_network` workflow, not
interruption analysis. Captured here from the 2025 CEB map review so it is not
lost.

- The CEB map colours lines by construction class: red = 66 kV, blue =
  "132 kV transmission operating at 66 kV". `PowerGrid.shp` does not carry this;
  the distinction lives only in `network_map_2025.png`.
- Model everything at the operating voltage (bus `v_nom = 66`). In the linear
  ("DC") OPF, PyPSA converts ohmic reactance to per-unit on a `v_nom^2` base, so
  stamping 132 kV on the blue spans would cut their per-unit reactance ~4x and
  distort the KVL flow split; it would also create mixed-voltage buses that
  need explicit 66/132 transformers. Keep 66 kV uniform.
- Record the design class as provenance only: a `design_voltage_kv` (66/132)
  column from a small reference table transcribed from the map, keyed by
  substation span (same pattern as `CEB_SUBSTATION_NAMES`). It carries through to
  netCDF and is ignored by the solver. The blue-span list still needs a review
  pass against the map.
- The 132 kV matters for resilience through capacity, not voltage: at 66 kV a
  conductor carries ~half its 132 kV MVA. Represent the upside as an explicit
  "uprate blue corridor" scenario (on tagged spans: `v_nom -> 132`,
  `s_nom -> ~2x`, add transformer coupling) and compare unserved energy against
  the 66 kV base.
- Prerequisite for any of the above to change results: replace the flat
  10,000 MVA `topology_capacity_mva` placeholder with real per-line 66 kV
  thermal ratings (conductor ampacity). Until then no line limit binds.

### Estimating the location of demand

The actual distribution system is not available. Use:

- OSM mapped distribution infrastructure where present;
- nightlight-supported road estimates for areas where mapping is missing;
- population, customer or economic data when available.

These data help divide demand and customer impacts between substations. Do not
insert unconfirmed inferred lines into the electrical network calculation or
give them assumed capacities.

Nightlight targets identify likely electrified areas from night-time lights;
the OSM roads near them are retained. Keep a `source` column so users can
distinguish inferred estimates from OSM mapping and CEB data.

For a distribution-network experiment, keep inferred routes out of the
reviewed baseline and label the alternative topology as inferred. Start with
graph connectivity and downstream demand disconnection. Distribution
power-flow cases require separate voltage-level buses and transformers, plus
named sensitivity sets for assumed feeder capacities and impedances.

## Notebook separation

Primary interruption-model notebooks:

1. `00-data-review/00_data_review.ipynb` reads the provided files, lists
   the records found, shows substation snap distances and identifies missing
   power-station information. It does not build a model.
2. `01-build-network/00_build_network.ipynb` builds or loads one selected
   network, validates its NetCDF/GeoParquet parity and saves a static PNG plus
   an interactive HTML map.
3. `02-interruption-analysis/00_interruption_analysis.ipynb` loads a saved
   `networks/<source>/<source>.nc` file and runs baseline/outage cases without
   rebuilding source-specific network inputs.

The line geometry does not provide an engineering circuit register, but it does
provide a meaningful topology. The base builder nodes routes at intersections
and snapped substations, labels connectors across mapped gaps of at most 75 m,
and uses non-binding line ratings until engineering ratings are available.

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
automatically overwrite provided or CEB records.

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
- Review generated topology connectors and replace proxy line ratings when CEB
  circuit ratings become available.
- Add voltage, circuit count and maximum power for lines and transformers.
- Complete unmatched generator capacities and replace neutral VoLL dispatch
  costs with sourced operating costs when cost analysis is required.
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
data/1-processed/energy/provided/
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
data/1-processed/energy/provided/
  generator_availability.csv
  generator_profile_assignments.csv
  generator_profile_metadata.json
```

### Priority 4: connect preparation, model build and outage runs

- The `build-network base` command derives the PyPSA topology from snapped
  substations, provided route geometry and complete rows in generated
  `generators.csv`; it does not attach demand.
- The `run-interruptions` command requires a saved network with `--network` or
  `--network-source`, then attaches demand and service weights. It does not
  rebuild topology from `lines.csv` or `generators.csv`.
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
  labelled topology-only graph from precomputed and OSM distribution lines.
- The two named inferred builders use VIIRS nightlight targets to filter a
  dense, cyclic OSM road subnetwork rather than publishing a sparse connector
  tree. `inferred-data` also retains the reviewed CEB backbone and carries
  complete reviewed generator rows; `inferred-osm` keeps OSM generator sites
  as capacity-free topology terminals. Neither product attaches demand.
- The standalone graph command writes nodes and edges under
  `data/1-processed/energy/inferred_distribution/`; the saved-network builder
  packages its graph tables under
  `data/1-processed/energy/networks/<result>/inferred_distribution/` and its
  spatial bundle under `<result>/geoparquet/`.
- Stage A is connectivity only: remove failed power terminals or feeder edges
  and count proxy demand disconnected from every remaining power root.
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

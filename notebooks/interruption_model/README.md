# Interruption-model notebooks

These notebooks guide preparation of the existing Mauritius electricity
network for interruption analysis.

The workflow is fixed-capacity rather than capacity-optimising. The current
input tables describe the existing system, but a reviewed future system can be
run through the same `EnergyModel().simulate(network, disruptions)` interface
if its assets, demand and disruptions are supplied explicitly.

## Before running

1. Activate `.venv` and install the package with `pip install -e .`.
2. Place the expected collaborator folders under
   `data/0-incoming/energy/collaborator/`, or set `MU_STAR_DATA_ROOT`.
3. Keep raw files unchanged.

## Run order

1. `00_data_intake.ipynb`
   - reads the demand workbook and mapped source files;
   - writes cleaned tables to `data/1-processed/energy/collaborator`;
   - snaps every substation to the nearest transmission route and reports the
     movement distances;
   - creates a power-station register and identifies missing maximum output,
     running cost and connected-substation information.
2. `01_operational_network.ipynb`
   - displays the transmission routes with the snapped substations;
   - does not derive electrical connections from route proximity;
   - labels routes where source voltage or power-rating fields are populated;
   - can use OSM and GridFinder to estimate each substation's share of demand;
   - reports whether line capacities, generation data and demand are ready.
3. `02_interruption_analysis.ipynb`
   - loads the supplied generator, line and demand files when they are present;
   - shows how `damage_to_disruptions(...)` converts asset damage into the
     standard mu-star disruption table;
   - builds a fixed-capacity baseline network when the required files exist;
   - compares normal operation with outage cases and writes result tables under
     `data/2-out/energy/`;
   - documents a staged, inferred GridFinder distribution-network experiment.

## User instructions

Review the generated records against CEB reports and collaborator knowledge.
The method used to share demand can be changed; record this choice. Avoid
estimating a power station's output from the size of its mapped polygon or
treating visually adjacent routes and substations as an electrical connection.
All substations are snapped to a route because the map is coarse. The warning
table highlights movements over 75 m, but does not exclude those substations.

The intake notebook reloads the local package when its first cell runs. This
prevents an open Jupyter kernel from retaining the previous `data/incoming`
path after the folders were renamed. If the first cell reports missing data,
its message lists the exact files and source directory being checked.

For simulation, copy `generation_register_template.csv` to
`generators.csv` and populate `generator_id`, `bus_id`, `carrier`,
`capacity_mw`, and `marginal_cost`. Supply `demand_profile.csv` either as a
system `demand_mw` series or as one complete column per substation.

Add `lines.csv` when an agreed source provides each line's endpoint
substations, voltage, length and maximum power. The repository does not create
this table from the mapped route geometry.

The route table includes `v_nom_kv`, `capacity_mw`, and `capacity_unit` columns
for source voltage and MW line-rating values. These stay blank where the
supplied route data do not state those values.

The `build-network` CLI now writes saved PyPSA handoff files for the upcoming
notebook split:

```bash
mu-star-energy build-network base
mu-star-energy build-network inferred --allow-provisional-demand
```

The reviewed `base` source requires `lines.csv`, `generators.csv`, and
`demand_profile.csv`. The `inferred` source is explicitly labelled and remains
separate from the reviewed base network.

The `run-interruptions` CLI reads `demand_profile.csv`, builds the reviewed
fixed-capacity network, runs a baseline case, and can then apply a disruption
CSV. The notebook `02_interruption_analysis.ipynb` still shows the current
Python route: load the supplied system files, convert damage to a disruption
table when needed, run a baseline case, and then test outage scenarios. In the
wider mu-star architecture this is the component-model step between hazard and
damage calculations upstream and indirect-loss or viewer steps downstream. The
network-building function can use a time-varying demand table when called from
Python. It supports regular half-hourly, hourly and three-hourly profiles and
sets their duration from the timestamp spacing.

GridFinder is currently used only as a demand-location proxy. The interruption
notebook describes a separate experimental path that converts inferred routes
to a graph, anchors feeders to reviewed substations and first tests downstream
disconnection. Electrical distribution power flow should only follow after
transformer support and explicit voltage, capacity and impedance sensitivity
cases are added.

The separate command
`mu-star-energy prepare-inferred-distribution --enable-inferred-distribution`
builds that labelled topology-only graph when GridFinder or OSM distribution
line files are available. Its outputs are written under
`data/1-processed/energy/inferred_distribution/` and must stay separate from
the reviewed `lines.csv` register.

For eventual delivery into `nismod/mu-star`, this package maps to
`src/energy`. Local data stages map as `0-incoming -> incoming`,
`1-processed -> processed`, and `2-out -> out`. The disruption adapter should
convert mu-star damage fractions to `available_fraction = 1 - damage_fraction`
before calling the energy model.

The column names are kept because the code needs them:

- `bus_id` means the connected substation;
- `carrier` means the fuel or technology;
- `capacity_mw` means maximum electrical output in `MW_e`;
- `capacity_basis` must be `electrical_output`;
- `marginal_cost` means the cost of producing one additional `MWh_e`;
- `fuel_energy_basis` records LHV or HHV when fuel assumptions are used;
- `s_nom_mva` is line or transformer apparent-power capacity;
- `source_route_id` optionally links a reviewed line to the mapped geometry so
  its voltage and capacity can appear on the network map.

The maps show capacity labels only when reviewed values exist. At present the
generator template contains no capacities and the line register is absent.
Voltage labels can come from route names or populated route columns; missing
power-rating labels mean missing input data, not zero capacity.

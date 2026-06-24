# Asset-model notebooks

These notebooks guide preparation of the existing Mauritius electricity
network for interruption analysis.

## Before running

1. Activate `.venv` and install the package with `pip install -e .`.
2. Place the expected collaborator folders under
   `data/0-incoming/energy/collaborator/`, or set `MU_STAR_DATA_ROOT`.
3. Keep raw files unchanged.

## Run order

1. `00_data_intake.ipynb`
   - reads the demand workbook and mapped source files;
   - writes cleaned tables to `data/1-processed/energy/collaborator`;
   - creates a power-station register and identifies missing maximum output,
     running cost and connected-substation information.
2. `01_operational_network.ipynb`
   - proposes which substations are connected by each mapped route;
   - can use OSM and GridFinder to estimate each substation's share of demand;
   - reports whether line capacities, generation data and demand are ready.

## User instructions

Review the generated records against CEB reports and collaborator knowledge.
The distance used to match a route to a substation and the method used to share
demand can be changed; record these choices. Avoid estimating a power station's
output from the size of its mapped polygon or presenting proposed line
connections as confirmed CEB circuits.

The intake notebook reloads the local package when its first cell runs. This
prevents an open Jupyter kernel from retaining the previous `data/incoming`
path after the folders were renamed. If the first cell reports missing data,
its message lists the exact files and source directory being checked.

For simulation, copy `generation_register_template.csv` to
`existing_generators.csv` and populate `generator_id`, `bus_id`, `carrier`,
`capacity_mw`, and `marginal_cost`. Supply `demand_profile.csv` either as a
system `demand_mw` series or as one complete column per substation.

The present workflow checks for `demand_profile.csv` but does not yet read it
and run the final outage calculation automatically. The network-building
function can use a time-varying demand table when called from Python. It
supports regular half-hourly, hourly and three-hourly profiles and sets their
duration from the timestamp spacing.

The column names are kept because the code needs them:

- `bus_id` means the connected substation;
- `carrier` means the fuel or technology;
- `capacity_mw` means maximum output;
- `marginal_cost` means the cost of producing one additional MWh.

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
   - reads the demand workbook and geospatial source layers;
   - writes reproducible tables to `data/1-processed/energy/collaborator`;
   - creates a register template and identifies missing capacities, marginal
     costs and bus assignments.
2. `01_operational_network.ipynb`
   - converts route geometry and substation points into a provisional graph;
   - optionally derives service weights from OSM/GridFinder;
   - reports whether ratings, generation and demand are ready for simulation.

## User responsibility

The user must reconcile generated records against CEB reports and collaborator
knowledge. Topology tolerances and service-weight methods may be changed, but
the resulting assumptions must be documented. Do not infer capacity from
geometry or treat provisional routes as validated circuits.

For simulation, copy `generation_register_template.csv` to
`existing_generators.csv` and populate `generator_id`, `bus_id`, `carrier`,
`capacity_mw`, and `marginal_cost`. Supply `demand_profile.csv` either as a
system `demand_mw` series or as complete bus columns.

# 1 - Processed data

These cleaned files are generated from `data/0-incoming/`. They are not stored
in git and should be possible to rebuild by running the preparation commands.

The energy model writes:

```text
data/1-processed/energy/
  collaborator/
    substations.parquet
    snapped_substations.parquet
    substation_snap_distances.csv
    transmission_routes.parquet
    generation_points.parquet
    generation_areas.parquet
    generation_register_template.csv
    monthly_peak_demand_mw.csv
    annual_sector_demand_gwh.csv
  inferred_distribution/
    inferred_distribution_nodes.csv
    inferred_distribution_edges.csv
    inferred_distribution_metadata.json
```

Files required before the model can calculate electricity supply:

- `existing_lines.csv`, with `line_id`, `bus0`, `bus1`, `v_nom_kv`,
  `length_km`, and `s_nom_mva`;
- `existing_generators.csv` with populated `generator_id`, `bus_id`, `carrier`,
  `capacity_mw`, and `marginal_cost`;
- `demand_profile.csv`, with dates and times, containing either one system-wide
  `demand_mw` column or one complete demand column per substation;
- `service_weights.csv`, giving every substation a share of total demand. The
  shares must add to one.
- optional `generator_availability.csv`, with dates and times plus one
  availability-fraction column per `generator_id`;
- optional `disruptions.csv`, with `component`, `asset_id`, and
  `available_fraction`, or a damage-fraction column that can be converted to
  available fraction.

Column meanings:

- `generator_id`: unique ID for a power station or generating unit;
- `bus_id`: unique ID for the connected substation;
- `carrier`: fuel or technology, such as hydro, solar or oil;
- `capacity_mw`: maximum electrical output in `MW_e`, mapped directly to
  `Generator.p_nom`;
- `capacity_basis`: must be `electrical_output`;
- `capacity_unit`: `MW_e`;
- `marginal_cost`: cost of producing one additional `MWh_e`;
- `marginal_cost_basis`: `electrical_output`;
- `fuel_energy_basis`: record `LHV` or `HHV` when a thermal fuel price or
  efficiency is used;
- `s_nom_mva`: maximum apparent power carried by a line.
- `v_nom_kv`: nominal voltage in kV. Lines at different voltages require
  separate buses connected by a transformer.

The asset model does not store generator capacity on an LHV fuel-input basis.
If a fuel price is supplied per thermal MWh on an LHV basis, convert it to
electrical marginal cost using the documented generator efficiency. PyPSA
`Link.p_nom`, used for explicit conversion technologies, is instead input-side
power at `bus0`. PyPSA does not select LHV or HHV automatically, so
`fuel_energy_basis` must record the source convention.

The current network builder creates AC lines but does not yet read a separate
transformer register. Mixed voltage levels therefore require a later
transformer extension rather than being combined into one bus.

Add `source_route_id` to `existing_lines.csv` when a reviewed electrical line
can be linked to a route in `transmission_routes.parquet`. The network map uses
this optional field to display reviewed kV and MVA values on the corresponding
route. Without it, the table remains usable by the model but cannot be placed
on the source-route map.

The model-building Python function and `run-interruptions` CLI accept these
time-varying demand values. Regular half-hourly, hourly and three-hourly
profiles are supported; the model sets the time-step duration from the
timestamp spacing. The same timestamp convention is used by
`generator_availability.csv` when supplied.

Copy `generation_register_template.csv` to `existing_generators.csv`, then
review and complete it rather than editing generated Parquet outputs by hand.
Keep the same generator IDs. Include the source and a short note for any value
that you add or correct manually.

`transmission_routes.parquet` preserves the supplied vector line geometry for
mapping and comparison. It includes `v_nom_kv`, `capacity_mw`, and
`capacity_unit` columns so explicit source voltage or MW line-rating values can
be carried through when present. These fields remain blank when the supplied
route data do not state them. The route geometry is not converted into
`existing_lines.csv` because the source attributes do not identify electrical
endpoint substations or complete line ratings. Add `existing_lines.csv` when
those data are available from an agreed source.

`substations.parquet` preserves the source point coordinates.
`snapped_substations.parquet` moves every point to the nearest mapped
transmission route for later network construction.
`substation_snap_distances.csv` records the original coordinates, matched route
part and movement distance so coarse or questionable alignments remain visible.
Every substation is snapped. The 75 m warning used in the intake notebook only
highlights movements for attention; it does not exclude a point.

The optional `inferred_distribution/` files are produced only by the explicit
inferred scenario command. They are connectivity-only GridFinder/OSM graph
tables for review and are not confirmed electrical line assets.

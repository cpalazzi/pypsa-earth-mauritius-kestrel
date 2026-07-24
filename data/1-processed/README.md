# 1 - Processed data

These cleaned files are generated from `data/0-incoming/`. They are not stored
in git and should be possible to rebuild by running the preparation commands.

The energy model writes:

```text
data/1-processed/energy/
  provided/
    substations.parquet
    snapped_substations.parquet
    substation_snap_distances.csv
    transmission_routes.parquet
    generation_points.parquet
    generation_areas.parquet
    generators.csv
    service_weights.csv
    monthly_peak_demand_mw.csv
    annual_sector_demand_gwh.csv
  templates/
    generators.csv
    lines.csv
```

Built networks are model outputs, not processed inputs, so they live under
`data/2-out/energy/networks/<name>/` (the PyPSA `.nc`, metadata, GeoParquet
bundle, review CSV tables and maps), not here.

Prepared evidence used to build the base network:

- `snapped_substations.parquet`, containing all provided substations aligned to
  transmission routes;
- `transmission_routes.parquet`, used to derive route sections and junctions;
- generated `generators.csv`, containing mapped sites, nearest-substation
  assignments and report-backed capacity where a clear match exists;

Run-time inputs attached to the saved network during interruption analysis:

- `demand_profile.csv`, with dates and times, containing either one system-wide
  `demand_mw` column or one complete demand column per substation;
- generated `service_weights.csv`, giving every substation a share of total
  demand. The fallback is equal shares and is labelled
  `equal_no_distribution_proxy`; the shares must add to one.
- optional `generator_availability.csv`, with dates and times plus one
  availability-fraction column per `generator_id`;
- optional `disruptions.csv`, with `component`, `asset_id`, and
  `available_fraction`, or a damage-fraction column that can be converted to
  available fraction.

Column meanings:

- `generator_id`: unique ID for a power station or generating unit;
- `bus_id`: unique ID for the connected substation;
- `carrier`: fuel or technology, such as hydro, solar or oil;
- `output_capacity_mw`: maximum electrical output in `MW_e`, mapped internally
  to `Generator.p_nom`;
- `capacity_basis`: optional audit field; when present, it must be
  `electrical_output`;
- `capacity_unit`: optional audit field, normally `MW_e`;
- `marginal_cost`: cost of producing one additional `MWh_e`; the generated
  value is currently zero only as an equal-dispatch VoLL proxy;
- `marginal_cost_basis`: records whether the value is an electrical operating
  cost or the temporary VoLL proxy;
- `fuel_energy_basis`: record `LHV` or `HHV` when a thermal fuel price or
  efficiency is used;
- `s_nom_mva`: maximum apparent power carried by a line.
- `v_nom_kv`: nominal voltage in kV. Lines at different voltages require
  separate buses connected by a transformer.

The model does not store generator capacity on an LHV fuel-input basis.
If a fuel price is provided per thermal MWh on an LHV basis, convert it to
electrical marginal cost using the documented generator efficiency. PyPSA
`Link.p_nom`, used for explicit conversion technologies, is instead input-side
power at `bus0`; a future human-facing Link table should therefore call this
`input_capacity_mw`. PyPSA does not select LHV or HHV automatically, so
`fuel_energy_basis` must record the source convention.

The current network builder creates AC lines but does not yet read a separate
transformer register. Mixed voltage levels therefore require a later
transformer extension rather than being combined into one bus.

Generated `lines.csv` retains `source_route_id` and `source_route_part_id` where
a section comes from provided geometry. Short gap connectors have
`source=derived_route_gap`, making the geometric assumption reviewable.

The model-building Python function and `run-interruptions` CLI accept these
time-varying demand values. Regular half-hourly, hourly and three-hourly
profiles are supported; the model sets the time-step duration from the
timestamp spacing. The same timestamp convention is used by
`generator_availability.csv` when provided.

`energy/provided/generators.csv` is generated directly; there is no separate
generation-site register. It retains incomplete rows for review, while the
base network includes only rows with `bus_id`, `carrier`,
`output_capacity_mw`, and `marginal_cost`. The templates document the portable
CSV schemas for importing replacement data or migrating into mu-star.

Older prepared data trees may still contain
`generation_register_template.csv`. It is no longer read; rerun
`prepare-assets` and use the generated `generators.csv`.

`transmission_routes.parquet` preserves the provided vector line geometry for
mapping and comparison. It includes `v_nom_kv`, `capacity_mw`, and
`capacity_unit` columns so explicit source voltage or MW line-rating values can
be carried through when present. These fields remain blank when the provided
route data do not state them. The base builder nodes this geometry at snapped
substations and route intersections, bridges mapped breaks of at most 75 m,
and writes the resulting `lines.csv` under `data/2-out/energy/base/`. Its high
`s_nom_mva` value is explicitly labelled as a non-binding topology proxy until
engineering ratings are available.

`substations.parquet` preserves the source point coordinates.
`snapped_substations.parquet` moves every point to the nearest mapped
transmission route for later network construction.
`substation_snap_distances.csv` records the original coordinates, matched route
part and movement distance so coarse or questionable alignments remain visible.
Every substation is snapped. The 75 m warning used in the intake notebook only
highlights movements for attention; it does not exclude a point.

The optional `inferred_distribution/` files are produced only by the explicit
inferred network build. They are connectivity-only nightlight/OSM graph tables
for review and are not confirmed electrical line assets. `inferred.nc` is a
PyPSA network derived from nightlight-supported OSM roads for testing; it
remains inferred and separate from the reviewed `base.nc` network.

Each network build also writes the same human-facing tables and an advisory
validation report under `data/2-out/energy/<source>/`. For example,
`base/{generators.csv,lines.csv,validation.json}` is derived from reviewed base
inputs, while `inferred/{generators.csv,lines.csv,validation.json}` records what
the inferred workflow actually built. Base validation compares total line
length with CEB's published 478.9 km 66 kV total and warns when the configured
tolerance is exceeded; it does not treat that comparison as like-for-like
engineering proof. It also compares the capacity of generators actually
included in the network with the CEB Annual Report 2023-2024 installed-capacity
grand total of 881.56 MW, including an explicit model coverage fraction and
scope note.

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

Column meanings:

- `generator_id`: unique ID for a power station or generating unit;
- `bus_id`: unique ID for the connected substation;
- `carrier`: fuel or technology, such as hydro, solar or oil;
- `capacity_mw`: maximum output in megawatts;
- `marginal_cost`: cost of producing one additional MWh;
- `s_nom_mva`: maximum apparent power carried by a line.

The model-building Python function accepts these time-varying demand values.
The automated workflow currently checks that the file exists but does not yet
read it and launch outage calculations. Regular half-hourly, hourly and
three-hourly profiles are supported; the model sets the time-step duration from
the timestamp spacing.

Copy `generation_register_template.csv` to `existing_generators.csv`, then
review and complete it rather than editing generated Parquet outputs by hand.
Keep the same generator IDs. Include the source and a short note for any value
that you add or correct manually.

`transmission_routes.parquet` preserves the supplied vector line geometry for
mapping and comparison. It is not converted into `existing_lines.csv` because
the source attributes do not identify electrical endpoint substations or line
ratings. Add `existing_lines.csv` when those data are available from an agreed
source.

`substations.parquet` preserves the source point coordinates.
`snapped_substations.parquet` moves every point to the nearest mapped
transmission route for later network construction.
`substation_snap_distances.csv` records the original coordinates, matched route
part and movement distance so coarse or questionable alignments remain visible.
Every substation is snapped. The 75 m warning used in the intake notebook only
highlights movements for attention; it does not exclude a point.

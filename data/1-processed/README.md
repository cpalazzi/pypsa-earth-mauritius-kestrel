# 1 - Processed data

These cleaned files are generated from `data/0-incoming/`. They are not stored
in git and should be possible to rebuild by running the preparation commands.

The energy model writes:

```text
data/1-processed/energy/
  collaborator/
    substations.parquet
    transmission_routes.parquet
    generation_points.parquet
    generation_areas.parquet
    generation_register_template.csv
    monthly_peak_demand_mw.csv
    annual_sector_demand_gwh.csv
  network/
    buses.parquet
    lines.parquet
    topology_report.json
```

Files required before the model can calculate electricity supply:

- `existing_generators.csv` with populated `generator_id`, `bus_id`, `carrier`,
  `capacity_mw`, and `marginal_cost`;
- the maximum power for each line in the `s_nom_mva` field;
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

Copy `generation_register_template.csv` to `existing_generators.csv`, then
review and complete it rather than editing generated Parquet outputs by hand.
Keep the same generator IDs. Include the source and a short note for any value
that you add or correct manually.

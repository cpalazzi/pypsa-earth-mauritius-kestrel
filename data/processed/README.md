# Processed data

Analysis-ready outputs generated from `data/incoming/`. Contents are ignored by
git and should be reproducible from the package or Snakemake workflow.

The energy model writes:

```text
data/processed/energy/
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

Files required before operational simulation can run:

- `existing_generators.csv` with validated capacities, carriers and bus links;
- line ratings populated in the topology `s_nom_mva` field;
- `demand_profile.csv`;
- `service_weights.csv`.


# 1 - Processed data

Analysis-ready outputs generated from `data/0-incoming/`. Contents are ignored
by git and should be reproducible from the package or Snakemake workflow.

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

Files required before operational simulation can run:

- `existing_generators.csv` with populated `generator_id`, `bus_id`, `carrier`,
  `capacity_mw`, and `marginal_cost`;
- line ratings populated in the topology `s_nom_mva` field;
- `demand_profile.csv`, indexed by timestamps, containing either `demand_mw`
  or one complete demand column per bus;
- `service_weights.csv`, covering every `bus_id` with weights summing to one.

Copy `generation_register_template.csv` to `existing_generators.csv`, then
review and complete it rather than editing generated Parquet outputs by hand.
Retain stable generator IDs, source references, and notes describing each
manual interpretation.

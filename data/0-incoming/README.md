# 0 - Incoming data

Raw source data are stored here or under an external data root configured with
`MU_STAR_DATA_ROOT`. Contents are ignored by git.

Expected energy layout:

```text
data/0-incoming/energy/
  collaborator/
    power_demand/
    power_transmission/
    substation/
    generation_source/
  gridfinder/
    grid.gpkg
  osm/
    distribution_lines.parquet
```

The collaborator folder currently comes from the project OneDrive export. Keep
source filenames unchanged and record any manual interpretation in processed
tables, not in the raw files.

GridFinder and OSM distribution data are used as spatial proxies for demand
service areas. They are not assumed to contain validated electrical parameters.

Users may change the data root with `MU_STAR_DATA_ROOT` or add new provider
subdirectories. If filenames or schemas change, update the intake code
explicitly rather than renaming source files to hide the difference.

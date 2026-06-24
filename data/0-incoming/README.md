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
source filenames unchanged. Record any judgement or correction in a new
cleaned table, not in the received file.

GridFinder and OSM line data can help estimate which areas may be served by
each substation. They do not provide confirmed line capacities, voltages or
other engineering details.

You can change the main data location with `MU_STAR_DATA_ROOT` or add folders
for new data providers. If a new file has different columns or a different
format, update the reading code and describe the difference. Do not rename the
source file to make it look like the old one.

# Project data

This is the single data tree for the Mauritius asset model:

```text
0-incoming  ->  1-processed  ->  2-out
```

- `0-incoming`: immutable source files from collaborators, OSM, GridFinder and
  other providers. Users place or sync source data here.
- `1-processed`: reproducible, analysis-ready asset, topology and demand
  tables. The package and workflow write this stage.
- `2-out`: baseline and disruption simulation outputs. Simulation code writes
  this stage.

Set `MU_STAR_DATA_ROOT` to place this same structure in a shared external
location. PyPSA-Earth baseline artifacts are separate and remain within
`pypsa-earth/`.

The numeric prefixes only control display order in file browsers. Do not add
parallel unnumbered stage directories.

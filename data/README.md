# Project data

This is the single data tree for the Mauritius asset model:

```text
incoming  ->  processed  ->  out
```

- `incoming`: immutable source files from collaborators, OSM, GridFinder and
  other providers.
- `processed`: reproducible, analysis-ready asset and demand tables.
- `out`: baseline and disruption simulation outputs.

Set `MU_STAR_DATA_ROOT` to place this same structure in a shared external
location. PyPSA-Earth baseline artifacts are separate and remain within
`pypsa-earth/`.

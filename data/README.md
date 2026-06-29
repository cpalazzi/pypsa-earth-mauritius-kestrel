# Project data

This is the single data tree for the Mauritius asset model:

```text
0-incoming  ->  1-processed  ->  2-out
```

- `0-incoming`: source files from collaborators or downloaded from
  OSM, GridFinder and other providers. Place or sync source data here and leave
  it unchanged.
- `1-processed`: cleaned tables of assets, network connections and demand.
  The preparation scripts write this stage.
- `2-out`: results from normal-operation and outage runs. The model writes this
  stage.

Set `MU_STAR_DATA_ROOT` to place this same structure in a shared external
location. PyPSA-Earth files are separate and remain within
`pypsa-earth/`.

The numeric prefixes only control display order in file browsers. Do not add
parallel unnumbered stage directories.

When the package is delivered into `nismod/mu-star`, these local stage names
map to mu-star's unnumbered folders:

```text
0-incoming   ->  incoming
1-processed  ->  processed
2-out        ->  out
```

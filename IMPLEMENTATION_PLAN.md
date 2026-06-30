# Implementation plan: decouple demand + OSM-road inferred network

Audience: an implementing agent. Work in the repo
`pypsa-earth-mauritius-kestrel` (Python 3.10 `.venv`, package `mu_star_energy`).
Run from a clean tree (`git status` clean). Tests: `.venv/bin/pytest`.
Do not commit notebook outputs (`.venv/bin/nbstripout <notebook>` before commit).
Do not add live-network calls to tests. Keep `EnergyModel.simulate(network,
disruptions)` stable and keep `assert_fixed_capacity(network)` passing.

## Current state (verified)

- `network.py`: `build_operational_network(buses, lines, generators,
  demand_profile, service_weights, *, generator_availability=None,
  value_of_lost_load=10_000, line_resistance_ohm_per_km=0.01,
  line_reactance_ohm_per_km=0.4) -> pypsa.Network`. It creates buses, AC lines,
  generators, **then** sets snapshots from `demand_profile`, adds per-bus `Load`
  and high-cost `load_shedding` generators sized to demand, and applies
  `generator_availability`. `assert_fixed_capacity(network)` rejects any
  extendable capacity.
- `network_source.py`: `build_network(source, *, input_dir=None,
  output_dir=None, generator_availability_path=None, gridfinder_lines_path=None,
  osm_distribution_lines_path=None, allow_pypsa_earth_osm_fallback=True,
  allow_provisional_demand=False, max_anchor_distance_m=500,
  inferred_voltage_kv=11, inferred_capacity_mva=5, value_of_lost_load=10_000)`.
  Saves `<source>.nc` + `<source>_metadata.json` to
  `data/1-processed/energy/networks/`. `base` requires `lines.csv`,
  `generators.csv`, `demand_profile.csv`, `service_weights.csv`,
  `snapped_substations.parquet`. `inferred` builds a graph (via
  `distribution_network.build_inferred_distribution_graph`), currently from
  GridFinder/OSM files **or the PyPSA-Earth mainland OSM fallback**
  (`_fallback_pypsa_earth_osm_lines`), with a provisional one-snapshot demand.
- `runner.py`: `run_interruption_analysis(input_dir, output_dir, *,
  network_path=None, ...)`. If `network_path` is given it loads the saved
  network and simulates **as-is** (assumes demand already baked in); otherwise
  it builds from CSVs. CLI `run-interruptions` exposes `--network`.
- `osm.py` (already implemented): `fetch_osm_roads(island, *,
  network_type="drive", overwrite=False) -> OSMRoadsOutput`, `ISLANDS`
  (`mauritius`, `rodrigues`, `agalega`, `st_brandon`), `osm_roads_path(island)`.
  Caches `[source, island, geometry]` LineStrings to
  `data/0-incoming/energy/osm/<island>/roads.parquet`.
- Notebooks: `00-data-review/00_data_review.ipynb`,
  `01-build-network/00_build_network.ipynb` + `01_demand_settings.ipynb`
  (draft), `02-interruption-analysis/00_interruption_analysis.ipynb`.

## Part A — Demand is a separate step (network builds without demand)

Outcome: `build-network` produces a **topology-only** network (buses, lines,
generators; no snapshots/loads). Demand attaches later, at the interruption
step, from `demand_profile.csv`. So `00_build_network` succeeds with no demand.

### A1. `network.py` — split build into topology + demand
- Add `build_topology_network(buses, lines, generators, *,
  line_resistance_ohm_per_km=0.01, line_reactance_ohm_per_km=0.4) ->
  pypsa.Network`: everything up to and including generators (buses, AC carrier,
  AC lines, generators). No snapshots beyond PyPSA's default, no loads, no
  `load_shedding`. Call `assert_fixed_capacity` before returning. Keep the
  existing input validation for lines/generators columns.
- Add `attach_demand(network, demand_profile, service_weights, *,
  generator_availability=None, value_of_lost_load=10_000) -> pypsa.Network`:
  operate on a copy; set snapshots + `snapshot_weightings` from the
  `demand_profile` index (reuse `_time_step_hours`); add per-bus `Load` and
  `load_shedding` generators sized to demand (the current logic); apply
  `generator_availability`. Return the run-ready network.
- Re-express `build_operational_network(...)` as a thin wrapper:
  `attach_demand(build_topology_network(buses, lines, generators), demand_profile,
  service_weights, generator_availability=..., value_of_lost_load=...)`. This
  keeps existing callers/tests working.

### A2. `network_source.py` — build topology only
- `_build_base_network` and `_build_inferred_network` call
  `build_topology_network(...)` and save the topology `<source>.nc`. Remove the
  demand requirement from the base path (`BASE_REQUIRED_FILES` drops
  `demand_profile.csv`; base now needs `snapped_substations.parquet`,
  `lines.csv`, `generators.csv`, `service_weights.csv`).
- Remove demand from build: delete `allow_provisional_demand`,
  `_load_demand_profile`, `_latest_peak_demand_profile` use from build. Keep
  `_latest_peak_demand_profile` but move its use to the demand step (A4).
- Metadata: record `"has_demand": false` and drop snapshot counts (or set to 0).

### A3. `runner.py` — attach demand when loading a saved network
- In the `network_path is not None` branch, the loaded network is topology-only:
  read `demand_profile.csv` and `service_weights.csv` from `input_dir`
  (+ optional `generator_availability.csv`) and call `attach_demand(...)` before
  simulating. Remove the "availability is baked in" `ValueError`.
- Add a clear error if `demand_profile.csv` is missing when a saved network is
  supplied ("attach demand first; see 01_demand_settings").
- CLI `run-interruptions`: no signature change needed (it already reads
  `--input-dir`); ensure `--network` + demand from `--input-dir` works.

### A4. Notebooks
- `00_build_network.ipynb`: drop `demand_profile.csv` from the build-skip check
  (cell after "Information still needed"); base build now needs only `lines.csv`
  + `generators.csv`. Update the markdown to say demand is attached later.
- `01_demand_settings.ipynb` (currently a draft): make it the place that writes
  `demand_profile.csv` — reviewed CSV passthrough, or the provisional
  one-snapshot profile from `monthly_peak_demand_mw.csv` (reuse
  `_latest_peak_demand_profile`, moved to a public helper, e.g.
  `network_source.provisional_demand_profile(input_dir)` or a new
  `demand.py`). Label provisional output clearly.
- `02_interruption-analysis/00_interruption_analysis.ipynb`: load the topology
  `<source>.nc`, attach demand from `demand_profile.csv` + `service_weights.csv`,
  then `EnergyModel().simulate(...)`.

### A5. Tests
- Update `tests/test_network_source.py`: built `<source>.nc` is topology-only
  (no loads/snapshots); base no longer needs `demand_profile.csv`.
- Add `tests/test_network.py`: `build_topology_network` returns a fixed-capacity
  network with the right bus/line/generator counts and no loads; `attach_demand`
  adds snapshots + loads + `load_shedding`; the wrapper still equals the old
  behaviour.
- Update `tests/test_runner.py`: saved-network path now attaches demand.

Acceptance A: `mu-star-energy build-network base` (with lines/generators only,
no demand) writes `base.nc`; `mu-star-energy build-network inferred` writes a
topology network; `run-interruptions --network base.nc` attaches demand and
runs; `pytest` green.

## Part B — Build the OSM-road inferred network per island

Outcome: `build-network inferred --island rodrigues` fetches OSM roads via
`osm.py` and builds a labelled inferred topology network for that island.

### B1. `osm.py` — add power-feature fetch for anchors
- Add `fetch_osm_power_features(island, *, overwrite=False) -> Path` using
  `osmnx.features_from_place(ISLANDS[island], tags={"power": ["substation",
  "plant", "generator"]})`; cache to
  `data/0-incoming/energy/osm/<island>/power.parquet` (points/centroids with a
  `bus_id` like `<ISLAND>_SUB_001`). Handle empty results gracefully.

### B2. `network_source.py` — island-aware inferred build
- Add `island: str | None = None` to `build_network` and `_build_inferred_network`.
- When `island` is set: roads = `osm.fetch_osm_roads(island)`; substations =
  power features from B1, or — if none — a single provisional root node at the
  road network's largest-component centroid (label `provisional_root=True` in
  metadata). Build the graph with `build_inferred_distribution_graph(substations,
  osm_distribution_lines=roads, max_anchor_distance_m=...)`, then topology
  network via `build_topology_network` (Part A).
- When `island` is None: keep today's mainland behaviour (reviewed substations +
  GridFinder/OSM file or PyPSA-Earth fallback).
- Output naming: `inferred-<island>.nc` / `inferred-<island>_metadata.json`
  (mainland stays `inferred.nc`). Record `island`, `road_edges`,
  `anchored/unanchored`, `provisional_root` in metadata.

### B3. CLI
- `build-network`: add `--island` with `choices=sorted(osm.ISLANDS)`; pass to
  `build_network`. Keep `--no-pypsa-earth-osm-fallback` for the mainland path.

### B4. Tests (no live network)
- `tests/test_osm.py`: keep offline tests. Add a test that monkeypatches
  `osm.fetch_osm_roads`/`fetch_osm_power_features` to return small fixture
  GeoDataFrames and asserts `build_network("inferred", island="rodrigues", ...)`
  writes `inferred-rodrigues.nc` and an inferred metadata file. No Overpass calls.

Acceptance B: with OSM fetch monkeypatched in tests, the island inferred build
produces a labelled topology network and metadata; manually,
`build-network inferred --island rodrigues` works online (Rodrigues ~2k road
edges). St Brandon yields an empty/near-empty graph without error.

## Commits (two chunks)

1. `Decouple demand from network build (topology build + attach_demand)` — Part A.
2. `Build OSM-road inferred network per island` — Part B.

Run `.venv/bin/pytest` before each commit; strip notebook outputs; push after each.

## Guardrails

- `assert_fixed_capacity` must pass on every built/attached network.
- Inferred assets stay labelled (`inferred`/`source`); never merged into reviewed
  `base` inputs (`lines.csv`).
- Keep `EnergyModel.simulate(network, disruptions)` and the
  `component`/`asset_id`/`available_fraction` disruption schema stable.
- osmnx cache stays under the data tree (already set in `osm.py`).

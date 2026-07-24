# Mauritius energy network model

The Mauritius electricity component of the
[`mu-star`](https://github.com/nismod/mu-star) infrastructure risk workflow. It
measures how much demand goes unserved when existing energy assets are damaged
or taken out of service.

This is an operational model of a fixed set of assets.

## Two models in this repo

Two separate models sit side by side:
the development workflow for the mu-star energy component, and PyPSA-Earth for reference.

**Interruption model (primary)** — the mu-star `energy` component: code in
`src/mu_star_energy/`, notebooks in
`notebooks/00-data-review/`, `01-build-network/` and `02-interruption-analysis/`. Runs a
provided system and tests asset outages:

```text
source evidence -> prepared inputs -> PyPSA network -> outage cases -> unserved energy
```

The standard call is:

```python
result = EnergyModel().simulate(network, disruptions)
```

**PyPSA-Earth reference** — code in `pypsa-earth/`, notebooks in
`notebooks/pypsa-earth-analysis/`. An open-data build used for renewable profiles, GEGIS
demand and capacity-expansion comparisons. It is not the CEB asset record and
does not feed the interruption model.

## Repository layout

The energy interruption model (the deliverable) and a vendored PyPSA-Earth
reference sit side by side. Everything at the top level belongs to the energy
model except `pypsa-earth/`, `arc/` and `references/`.

```text
# Energy interruption model — delivered to mu-star as the `energy` component
├── src/mu_star_energy/      # Model code
├── config/                  # Model settings (energy.yaml) and damage curves
├── workflow/                # Snakemake preparation/run rules
├── data/                    # Model data: 0-incoming -> 1-processed -> 2-out
├── tests/
├── notebooks/
│   ├── 00-data-review/
│   ├── 01-build-network/
│   └── 02-interruption-analysis/

# PyPSA-Earth reference — with its own config/data inside
├── pypsa-earth/             # Vendored PyPSA-Earth code and outputs
├── arc/                     # Scripts to run PyPSA-Earth on the ARC cluster
├── references/              # Reference data sheets
└── notebooks/pypsa-earth-analysis/   # Notebooks exploring PyPSA-Earth runs
```

The energy model's `config/`, `workflow/`, `data/` and `src/` mirror the mu-star
component layout. PyPSA-Earth keeps its own `config/`, `data/`, `resources/` and
`results/` inside `pypsa-earth/`. Within `data/`, the numeric prefixes just keep
the stages sorted in a file browser.

## Glossary

- **Bus** — an electrical connection point; here, a snapped substation or a
  route junction.
- **Dispatch** — how much each station produces in a time step.
- **Snapshot** — one model time step (e.g. an hour).
- **Service weight** — a substation's share of total demand (shares sum to one).
- **Unserved energy / load shedding** — demand the system could not supply.

## Capacity conventions

- `output_capacity_mw` is a generator's electrical output in `MW_e`. The
  builder maps it to PyPSA `Generator.p_nom`; users do not need PyPSA column
  names in their CSVs.
- A future conversion `Link` input should use `input_capacity_mw`, because
  PyPSA `Link.p_nom` is rated at its input (`bus0`).
- `marginal_cost` is per `MWh_e`. For a thermal fuel priced per `MWh_fuel`
  (LHV), convert first — `fuel price / efficiency + variable operating cost` —
  and record the basis in `fuel_energy_basis`.
- `s_nom_mva` is a line's apparent-power rating in MVA; `v_nom_kv` is nominal
  voltage in kV.

The builder creates AC `Line` and `Generator` components only. See the
[PyPSA 0.30.3 components](https://docs.pypsa.org/v0.30.3/user-guide/components.html).

## Setup

Create a virtual environment (Python 3.10 or 3.11) and install the model:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Use the `.venv` kernel for the notebooks and run the tests with `.venv/bin/pytest`.
To also set up the vendored PyPSA-Earth reference, run `./local_setup.sh`, which
reuses the same `.venv`.

## Workflow

1. **Place source data** under `data/0-incoming/energy/provided/` (the
   `power_demand`, `power_transmission`, `substation` and `generation_source`
   folders described in `data/0-incoming/README.md`). Keep source files
   unchanged. To use a shared or OneDrive tree, set `MU_STAR_DATA_ROOT` to a
   directory with the same numbered stage folders.

2. **Prepare review tables:**

   ```bash
   .venv/bin/python -m mu_star_energy.cli prepare-assets
   ```

   This writes cleaned tables, including generated `generators.csv`, to
   `data/1-processed/energy/provided/` and header-only interchange schemas to
   `data/1-processed/energy/templates/`. Don't edit generated Parquet files by
   hand.

3. **Run the notebooks in order:** `00-data-review/` (clean and inspect source
   data), `01-build-network/` (build a saved network), `02-interruption-analysis/` (run
   baseline and outage cases).

4. **Build a network** (what `01-build-network/` calls):

   ```bash
   .venv/bin/python -m mu_star_energy.cli build-network base \
     --output-name base-mauritius --overwrite

   .venv/bin/python -m mu_star_energy.cli build-network inferred-osm \
     --region mauritius-rodrigues \
     --output-name inferred-osm-mauritius-rodrigues \
     --overwrite

   .venv/bin/python -m mu_star_energy.cli build-network inferred-data \
     --region mauritius-rodrigues \
     --output-name inferred-data-mauritius-rodrigues \
     --overwrite
   ```

   Each command writes one packaged result under
   `data/2-out/energy/networks/<name>/`: the canonical
   `<name>.nc`, metadata, and a `geoparquet/` bundle containing deterministic
   `<name>-nodes.geoparquet`, `<name>-edges.geoparquet` and
   `<name>-spatial-manifest.json`. NetCDF remains the modelling artifact; the
   checksum-linked EPSG:4326 GeoParquet files are its visualisation and GIS
   view. The build notebook writes static and interactive maps under the same
   result's `visualisations/` directory.

   `base` derives lines and junctions from the provided transmission routes and
   snapped substations, and includes generated generator rows whose required
   values are complete. It writes the canonical PyPSA
   network, the human CSVs and `validation.json` together under
   `data/2-out/energy/networks/base-mauritius/`.
   Incomplete generator records remain in the review CSV and produce warnings;
   they do not block the topology. The two inferred contracts share one routing
   method: VIIRS nightlights identify likely electrified targets, which then
   retain the dense, cyclic OSM all-ways subnetwork within the configured
   support distance.
   `inferred-osm` uses OSM substations, plants and generators as known power
   terminals. OSM generator sites remain topology terminals rather than PyPSA
   generators because reviewed capacity and operating attributes are absent.
   `inferred-data` replaces those terminals with the reviewed input substations
   and generator sites; complete reviewed generator records are also carried
   into PyPSA, and its reviewed CEB backbone is retained explicitly. A member
   island without a known terminal receives a labelled provisional root. The
   inferred road-plus-backbone length itself is checked against CEB's reported
   10,492.2 circuit-km total; the complete unfiltered road envelope remains an
   additional audit comparison.

5. **Run interruptions:**

   ```bash
   .venv/bin/python -m mu_star_energy.cli run-interruptions \
     --network data/1-processed/energy/networks/base-mauritius/base-mauritius.nc \
     --output-dir data/2-out/energy \
     --disruptions data/1-processed/energy/provided/disruptions.csv
   ```

   Omit `--disruptions` for a baseline-only run. Results and a `demand_summary.csv`
   are written under `data/2-out/energy/`. Equivalently, call
   `EnergyModel().simulate(network, disruptions)` in Python.
   This stage reads the packaged `base-mauritius.nc`; it does not rebuild the network from
   `lines.csv` or `generators.csv`.

### Generated inputs for `base`

The base builder consumes prepared source evidence rather than requiring a
manually created `lines.csv`:

- `snapped_substations.parquet` contains all provided substations aligned to
  the mapped transmission routes;
- `transmission_routes.parquet` supplies the route geometry. Local breaks of
  at most 75 m use a minimum connector tree, station endpoints within 100 m
  meet at one station node, and the 171.5 m Ebene–Wooton closure is an explicit
  CEB-map-reviewed join. Every connector remains labelled
  `derived_route_gap`; parallel source routes retain separate circuit IDs;
- `generators.csv` is generated from mapped station sites, nearest-substation
  assignment and clearly matched installed capacities in the
  [CEB Annual Report 2023-2024](https://ceb.mu/files/files/publications/Annual%20Report/CEB%20AR%202023-2024.pdf).
  Its `marginal_cost=0` values are a neutral VoLL dispatch proxy, not operating
  cost estimates. Rows without sourced capacity remain visible but are omitted
  from the saved network;
- `service_weights.csv` — each substation's share of demand (shares sum to one).
  Preparation writes an explicitly labelled equal-share fallback when no
  distribution proxy is available.
- `demand_profile.csv` — required when running interruptions, not when building
  the topology network. Use a timestamp column plus either one `demand_mw`
  column (split across substations by `service_weights.csv`) or one column per
  `bus_id`. Regular half-hourly, hourly or three-hourly spacing.

The provided workbook only provides monthly peaks and annual sector totals.
`01_demand_settings.ipynb` therefore creates a clearly labelled one-snapshot
provisional profile for a pipeline run; replace it with dated CEB or other
documented demand before interpreting reliability results.
Generated human-readable `lines.csv` and `generators.csv` snapshots are written
under `data/2-out/energy/base-mauritius/`. The advisory base validation also compares
modelled total line length with the
[CEB published 66 kV total](https://ceb.mu/fact-sheets/grid-infrastructure)
(442 km overhead plus 36.9 km underground). It
warns rather than fails because mapped route length and circuit length may use
different bases. It separately compares modelled generator output capacity
with the 881.56 MW installed-capacity grand total reported on pp. 50-51 of the
[CEB Annual Report 2023-2024](https://ceb.mu/files/files/publications/Annual%20Report/CEB%20AR%202023-2024.pdf).
That check reports the coverage fraction and notes that the CEB total includes
CEB, IPP, SSDG and MSDG generation.

## Nightlight and road inferred proxies

The low-voltage distribution network is unavailable, so both inferred builds
are connectivity proxies rather than claimed electrical networks. A high-pass
filter over the reviewed VIIRS composite marks bright cells as nightlight
targets; the dense OSM road subnetwork within the configured support distance
of those targets (and of known power assets) is retained, keeping a connected
Mauritius component and a connected Rodrigues component.

`inferred-osm` uses OSM `power=substation`, `power=plant` and
`power=generator` features as power terminals. `inferred-data` uses only the
reviewed input substations and generator coordinates. Road lengths and anchor
distances are measured geodesically on WGS84. The islands retain separate
region provenance and are never joined by a synthetic inter-island line.

The validation report separately builds a de-duplicated OSM all-ways road
envelope and compares its length with CEB's published 10,492.2 km total
(transmission, MV and LV). The retained nightlight-supported road subnetwork is
intentionally shorter; the envelope comparison is a coverage diagnostic, not evidence that
any individual road carries a power line.
The inferred GeoParquet keeps the 11 kV and 5 MVA topology placeholders in
explicit `model_*` columns but leaves the public voltage and capacity fields
null, so a visualisation cannot present them as observed electrical data.

The base metadata separately validates the closures visible on the supplied
CEB 2025 map. It counts only cycles with at least a 1 km² mapped footprint,
checks the Amaury, La Chaumiere and Ebene junctions, confirms that the two
reviewed return routes survive pruning, and verifies the preserved parallel
source path. The map's blue 132 kV construction class is explicitly marked as
operating at 66 kV, so PyPSA uses 66 kV as the electrical nominal voltage.
The source vectors do not retain enough map styling to assign the blue/red
design class to every exported circuit.

Power terminals are anchored to the nearest inferred route endpoint within
1,000 m. Unanchored terminals remain visible for review. The inferred products
remain separate from the reviewed CEB-derived `base` topology.

## Guardrails

- Don't change source files under `data/0-incoming/`.
- Don't present inferred or nightlight-supported lines as confirmed CEB data.
- Don't let the interruption model add new generation, lines or storage.

## PyPSA-Earth comparisons

See `notebooks/pypsa-earth-analysis/README.md`. These notebooks are read-only analysis:
pick the one relevant to your question and confirm compared runs share the same
assumptions (cost year, time-step length, carbon limit, technologies).

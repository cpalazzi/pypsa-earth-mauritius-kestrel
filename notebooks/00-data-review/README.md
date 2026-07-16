# Data review notebooks

Purpose: inspect provided source files, write cleaned review tables and
identify missing engineering inputs. This stage does not build a PyPSA network.

Inputs:

- `data/0-incoming/energy/provided/power_demand/`
- `data/0-incoming/energy/provided/substation/`
- `data/0-incoming/energy/provided/power_transmission/`
- `data/0-incoming/energy/provided/generation_source/`

Outputs:

- cleaned substations, snapped substations and snap-distance reports;
- transmission route geometry for review;
- generated generator table with report capacity and nearest-bus assignment;
- monthly peak and annual sector demand summaries.

Settings users may change: data root via `MU_STAR_DATA_ROOT`. Keep source files
unchanged.

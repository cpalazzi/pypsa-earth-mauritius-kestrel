# Data review notebooks

Purpose: inspect collaborator source files, write cleaned review tables and
identify missing engineering inputs. This stage does not build a PyPSA network.

Inputs:

- `data/0-incoming/energy/collaborator/power_demand/`
- `data/0-incoming/energy/collaborator/substation/`
- `data/0-incoming/energy/collaborator/power_transmission/`
- `data/0-incoming/energy/collaborator/generation_source/`

Outputs:

- cleaned substations, snapped substations and snap-distance reports;
- transmission route geometry for review;
- generation register template;
- monthly peak and annual sector demand summaries.

Settings users may change: data root via `MU_STAR_DATA_ROOT`. Keep source files
unchanged.

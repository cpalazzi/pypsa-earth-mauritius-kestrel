# 2 - Model outputs

Results for normal operation and asset outages are written here. Contents are
ignored by git.

Each result should record the case that was run, unavailable assets, whether
the calculation completed, operating cost, electricity demand not supplied,
the share of demand supplied, and impacts by substation or customer sector.

You can create one subfolder per outage case. A result should be possible to
recreate from the saved settings and cleaned input files. Do not place source
data or manually maintained asset registers here.

Network builds create source-specific review folders:

```text
energy/
  base/{generators.csv,lines.csv,validation.json}
  inferred/{generators.csv,lines.csv,validation.json}
```

These CSVs record the human-facing tables used to construct each saved PyPSA
network. They are generated outputs, not another place to maintain inputs.
For the base network, `validation.json` includes advisory comparisons against
published CEB transmission length and total installed generating capacity.

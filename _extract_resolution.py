"""Extract 1h vs 3h resolution comparison metrics."""
import pypsa
import pandas as pd
import numpy as np

base = "results/europe-year-140/networks/_resolution_sensitivity"
nets = {}
for label, fname in [
    ("3h", f"{base}/elec_s_140_ec_lcopt_Co2zero-3h-NH3-DEA30.nc"),
    ("1h", f"{base}/elec_s_140_ec_lcopt_Co2zero-1h-NH3-DEA30.nc"),
]:
    nets[label] = pypsa.Network(fname)
    n = nets[label]
    print(f"{label}: {len(n.snapshots)} snapshots, {len(n.buses)} buses")

print()
print("=" * 70)
print("  SYSTEM SUMMARY")
print("=" * 70)

lcoes = {}
for label, n in nets.items():
    sw = n.snapshot_weightings.objective.reindex(n.snapshots).fillna(1.0)
    demand_mwh = n.loads_t.p_set.mul(sw, axis=0).sum().sum()
    obj = float(getattr(n, "objective", float("nan")))
    lcoe = obj / demand_mwh if demand_mwh else float("nan")
    lcoes[label] = lcoe
    print(
        f"  {label}: demand={demand_mwh/1e6:.2f} TWh, "
        f"objective={obj/1e9:.3f} bn EUR, LCOE={lcoe:.2f} EUR/MWh"
    )

pct = (lcoes["1h"] - lcoes["3h"]) / lcoes["3h"] * 100
print(f"\n  LCOE difference (1h vs 3h): {pct:+.2f}%")

print()
print("=" * 70)
print("  ENERGY STORAGE CAPACITIES (GWh)")
print("=" * 70)

store_data = {}
for label, n in nets.items():
    store_col = "e_nom_opt" if "e_nom_opt" in n.stores.columns else "e_nom"
    store_cap = n.stores.groupby("carrier")[store_col].sum() / 1e3
    store_data[label] = store_cap
    print(f"\n  --- {label} ---")
    for c in store_cap.sort_values(ascending=False).index:
        print(f"    {c:25s}: {store_cap[c]:>10.1f} GWh")

print()
print("=" * 70)
print("  STORAGE DELTAS")
print("=" * 70)
for carrier in ["battery", "H2", "NH3"]:
    v3 = store_data["3h"].get(carrier, 0)
    v1 = store_data["1h"].get(carrier, 0)
    delta_pct = (v1 - v3) / v3 * 100 if v3 != 0 else float("nan")
    print(
        f"  {carrier:10s}: 3h={v3:>10.1f} GWh, 1h={v1:>10.1f} GWh, "
        f"delta={v1 - v3:>+10.1f} GWh ({delta_pct:+.1f}%)"
    )

print()
print("=" * 70)
print("  POWER CAPACITY DELTAS (GW)")
print("=" * 70)

for carrier in [
    "solar", "onwind", "offwind-ac", "offwind-dc",
    "battery charger", "battery discharger",
    "CCGT", "CCGT NH3", "nuclear", "coal",
    "H2 electrolysis", "NH3 synthesis", "NH3 pipeline", "H2 pipeline",
    "CCGT H2", "B2B", "oil", "ror",
]:
    vals = {}
    for label, n in nets.items():
        gen_col = "p_nom_opt" if "p_nom_opt" in n.generators.columns else "p_nom"
        link_col = "p_nom_opt" if "p_nom_opt" in n.links.columns else "p_nom"
        g = (
            n.generators[n.generators.carrier == carrier][gen_col].sum()
            if carrier in n.generators.carrier.values
            else 0
        )
        lk = (
            n.links[n.links.carrier == carrier][link_col].sum()
            if carrier in n.links.carrier.values
            else 0
        )
        vals[label] = (g + lk) / 1e3
    v3, v1 = vals["3h"], vals["1h"]
    if v3 == 0 and v1 == 0:
        continue
    delta_pct = (v1 - v3) / v3 * 100 if v3 != 0 else float("nan")
    print(
        f"  {carrier:25s}: 3h={v3:>8.1f} GW, 1h={v1:>8.1f} GW, "
        f"delta={v1 - v3:>+8.1f} GW ({delta_pct:+.1f}%)"
    )

# Spatial distribution analysis for battery
print()
print("=" * 70)
print("  BATTERY SPATIAL DISTRIBUTION (top 10 buses by delta)")
print("=" * 70)
store_col = "e_nom_opt"
for carrier in ["battery", "H2"]:
    caps = {}
    for label, n in nets.items():
        mask = n.stores.carrier == carrier
        if mask.any():
            caps[label] = n.stores.loc[mask].groupby("bus")[store_col].sum()
        else:
            caps[label] = pd.Series(dtype=float)
    if all(s.empty for s in caps.values()):
        continue
    comp = pd.DataFrame(caps).fillna(0)
    comp["delta_MWh"] = comp.get("1h", 0) - comp.get("3h", 0)
    comp["delta_%"] = (comp["delta_MWh"] / comp["3h"].replace(0, np.nan) * 100).round(1)
    comp = comp.sort_values("delta_MWh", key=abs, ascending=False)
    print(f"\n  --- {carrier} (top 10 by |delta|) ---")
    print(f"  System total: 3h={comp['3h'].sum()/1e3:,.1f} GWh, 1h={comp['1h'].sum()/1e3:,.1f} GWh")
    for bus, row in comp.head(10).iterrows():
        print(
            f"    {bus:30s}: 3h={row['3h']:>10,.0f} MWh, 1h={row['1h']:>10,.0f} MWh, "
            f"delta={row['delta_MWh']:>+10,.0f} MWh ({row['delta_%']:>+.1f}%)"
        )

# Dispatch comparison
print()
print("=" * 70)
print("  DISPATCH COMPARISON (TWh)")
print("=" * 70)
for label, n in nets.items():
    sw = n.snapshot_weightings.objective.reindex(n.snapshots).fillna(1.0)
    gen_mwh = n.generators_t.p.clip(lower=0.0).mul(sw, axis=0).sum()
    gen_mix = pd.DataFrame({"mwh": gen_mwh, "carrier": n.generators["carrier"]}).groupby("carrier")["mwh"].sum()
    non_dc = n.links[n.links.carrier != "DC"]
    link_p0 = n.links_t.p0.loc[:, n.links_t.p0.columns.isin(non_dc.index)]
    link_mwh = link_p0.clip(lower=0.0).mul(sw, axis=0).sum()
    link_mix = pd.DataFrame({"mwh": link_mwh, "carrier": non_dc["carrier"]}).groupby("carrier")["mwh"].sum()
    total = pd.concat([gen_mix, link_mix]).groupby(level=0).sum() / 1e6
    total = total.drop(index="load shedding", errors="ignore")
    print(f"\n  --- {label} ---")
    for c in total.sort_values(ascending=False).index[:12]:
        print(f"    {c:25s}: {total[c]:>8.1f} TWh")

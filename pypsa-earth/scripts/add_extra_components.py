# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# -*- coding: utf-8 -*-
"""
Adds extra extendable components to the clustered and simplified network.

Relevant Settings
-----------------

.. code:: yaml

    costs:
        year:
        version:
        rooftop_share:
        USD2013_to_EUR2013:
        dicountrate:
        emission_prices:

    electricity:
        max_hours:
        marginal_cost:
        capital_cost:
        extendable_carriers:
            StorageUnit:
            Store:

.. seealso::
    Documentation of the configuration file ``config.yaml`` at :ref:`costs_cf`,
    :ref:`electricity_cf`

Inputs
------

- ``resources/costs.csv``: The database of cost assumptions for all included technologies for specific years from various sources; e.g. discount rate, lifetime, investment (CAPEX), fixed operation and maintenance (FOM), variable operation and maintenance (VOM), fuel costs, efficiency, carbon-dioxide intensity.

Outputs
-------

- ``networks/elec_s{simpl}_{clusters}_ec.nc``:


Description
-----------

The rule :mod:`add_extra_components` attaches additional extendable components to the clustered and simplified network. These can be configured in the ``config.yaml`` at ``electricity: extendable_carriers:``. It processes ``networks/elec_s{simpl}_{clusters}.nc`` to build ``networks/elec_s{simpl}_{clusters}_ec.nc``, which in contrast to the former (depending on the configuration) contain with **zero** initial capacity

- ``StorageUnits`` of carrier 'H2' and/or 'battery'. If this option is chosen, every bus is given an extendable ``StorageUnit`` of the corresponding carrier. The energy and power capacities are linked through a parameter that specifies the energy capacity as maximum hours at full dispatch power and is configured in ``electricity: max_hours:``. This linkage leads to one investment variable per storage unit. The default ``max_hours`` lead to long-term hydrogen and short-term battery storage units.

- ``Stores`` of carrier 'H2' and/or 'battery' in combination with ``Links``. If this option is chosen, the script adds extra buses with corresponding carrier where energy ``Stores`` are attached and which are connected to the corresponding power buses via two links, one each for charging and discharging. This leads to three investment variables for the energy capacity, charging and discharging capacity of the storage unit.
"""
import os

import numpy as np
import pandas as pd
import pypsa
from _helpers import (
    configure_logging,
    create_logger,
    lossy_bidirectional_links,
    set_length_based_efficiency,
)
from add_electricity import (
    _add_missing_carriers_from_costs,
    add_nice_carrier_names,
    load_costs,
)

idx = pd.IndexSlice

logger = create_logger(__name__)


def attach_storageunits(n, costs, config):
    elec_opts = config["electricity"]
    carriers = elec_opts["extendable_carriers"]["StorageUnit"]
    max_hours = elec_opts["max_hours"]

    _add_missing_carriers_from_costs(n, costs, carriers)

    buses_i = n.buses.index

    lookup_store = {"H2": "electrolysis", "battery": "battery inverter"}
    lookup_dispatch = {"H2": "fuel cell", "battery": "battery inverter"}

    for carrier in carriers:
        n.madd(
            "StorageUnit",
            buses_i,
            " " + carrier,
            bus=buses_i,
            carrier=carrier,
            p_nom_extendable=True,
            capital_cost=costs.at[carrier, "capital_cost"],
            marginal_cost=costs.at[carrier, "marginal_cost"],
            efficiency_store=costs.at[lookup_store[carrier], "efficiency"],
            efficiency_dispatch=costs.at[lookup_dispatch[carrier], "efficiency"],
            max_hours=max_hours[carrier],
            cyclic_state_of_charge=True,
        )


def attach_stores(n, costs, config):
    elec_opts = config["electricity"]
    carriers = elec_opts["extendable_carriers"]["Store"]

    _add_missing_carriers_from_costs(n, costs, carriers)

    buses_i = n.buses.index
    bus_sub_dict = {k: n.buses[k].values for k in ["x", "y", "country"]}

    if "H2" in carriers:
        h2_buses_i = n.madd("Bus", buses_i + " H2", carrier="H2", **bus_sub_dict)

        n.madd(
            "Store",
            h2_buses_i,
            bus=h2_buses_i,
            carrier="H2",
            e_nom_extendable=True,
            e_cyclic=True,
            capital_cost=costs.at["hydrogen storage tank", "capital_cost"],
        )

        n.madd(
            "Link",
            h2_buses_i + " Electrolysis",
            bus0=buses_i,
            bus1=h2_buses_i,
            carrier="H2 electrolysis",
            p_nom_extendable=True,
            efficiency=costs.at["electrolysis", "efficiency"],
            capital_cost=costs.at["electrolysis", "capital_cost"],
            marginal_cost=costs.at["electrolysis", "marginal_cost"],
        )

        # Fuel cell removed — H2-to-power is handled by CCGT H2 links
        # (added via attach_hydrogen_ccgt when "CCGT H2" is in extendable_carriers.Link).
        # To re-enable fuel cells, uncomment the block below.
        #
        # n.madd(
        #     "Link",
        #     h2_buses_i + " Fuel Cell",
        #     bus0=h2_buses_i,
        #     bus1=buses_i,
        #     carrier="H2 fuel cell",
        #     p_nom_extendable=True,
        #     efficiency=costs.at["fuel cell", "efficiency"],
        #     capital_cost=costs.at["fuel cell", "capital_cost"]
        #     * costs.at["fuel cell", "efficiency"],
        #     marginal_cost=costs.at["fuel cell", "marginal_cost"],
        # )

    if "battery" in carriers:
        b_buses_i = n.madd(
            "Bus", buses_i + " battery", carrier="battery", **bus_sub_dict
        )

        n.madd(
            "Store",
            b_buses_i,
            bus=b_buses_i,
            carrier="battery",
            e_cyclic=True,
            e_nom_extendable=True,
            capital_cost=costs.at["battery storage", "capital_cost"],
            marginal_cost=costs.at["battery", "marginal_cost"],
        )

        n.madd(
            "Link",
            b_buses_i + " charger",
            bus0=buses_i,
            bus1=b_buses_i,
            carrier="battery charger",
            efficiency=costs.at["battery inverter", "efficiency"],
            capital_cost=costs.at["battery inverter", "capital_cost"],
            p_nom_extendable=True,
            marginal_cost=costs.at["battery inverter", "marginal_cost"],
        )

        n.madd(
            "Link",
            b_buses_i + " discharger",
            bus0=b_buses_i,
            bus1=buses_i,
            carrier="battery discharger",
            efficiency=costs.at["battery inverter", "efficiency"],
            p_nom_extendable=True,
            marginal_cost=costs.at["battery inverter", "marginal_cost"],
        )

    if ("csp" in elec_opts["renewable_carriers"]) and (
        config["renewable"]["csp"]["csp_model"] == "advanced"
    ):
        # add separate buses for csp
        main_buses = n.generators.query("carrier == 'csp'").bus
        csp_buses_i = n.madd(
            "Bus",
            main_buses + " csp",
            carrier="csp",
            x=n.buses.loc[main_buses, "x"].values,
            y=n.buses.loc[main_buses, "y"].values,
            country=n.buses.loc[main_buses, "country"].values,
        )
        n.generators.loc[main_buses.index, "bus"] = csp_buses_i

        # add stores for csp
        n.madd(
            "Store",
            csp_buses_i,
            bus=csp_buses_i,
            carrier="csp",
            e_cyclic=True,
            e_nom_extendable=True,
            capital_cost=costs.at["csp-tower TES", "capital_cost"],
            marginal_cost=costs.at["csp-tower TES", "marginal_cost"],
        )

        # add links for csp
        n.madd(
            "Link",
            csp_buses_i,
            bus0=csp_buses_i,
            bus1=main_buses,
            carrier="csp",
            efficiency=costs.at["csp-tower", "efficiency"],
            capital_cost=costs.at["csp-tower", "capital_cost"],
            p_nom_extendable=True,
            marginal_cost=costs.at["csp-tower", "marginal_cost"],
        )


def attach_ammonia_stores(n, costs, config):
    """
    Add NH3 buses, stores and ammonia-synthesis links at every AC bus that
    already has a hydrogen bus.

    NH3 synthesis link:
      bus0 = H2 bus  (hydrogen consumed)
      bus1 = NH3 bus (ammonia produced)
      bus2 = AC bus  (electricity consumed for Haber-Bosch)

    From DEA 2030 archived config the stoichiometric recipe is:
      1.13472 MWh_H2 + 0.16 MWh_el  →  1.0 MWh_NH3
    which translates to PyPSA link coefficients on a per-unit-H2 basis:
      efficiency  = 1 / 1.13472 ≈ 0.881   (NH3 out per H2 in)
      efficiency2 = -0.16 / 1.13472 ≈ -0.141  (AC drawn per H2 in)

    Operational constraints reflect Haber-Bosch process limitations:
      p_min_pu       = 0.3   (minimum stable load ~30% of nameplate)
      ramp_limit_up  = 0.1   (10% of p_nom per snapshot, ~30%/h at 3-h res)
      ramp_limit_down= 0.1   (symmetric)
    """
    elec_opts = config["electricity"]
    ext_carriers = elec_opts["extendable_carriers"]
    as_stores = ext_carriers.get("Store", [])

    if "NH3" not in as_stores:
        return

    assert "H2" in as_stores, (
        "Attaching ammonia stores requires hydrogen storage to be modelled "
        "as Store-Link-Bus combination. Add 'H2' to "
        "`electricity.extendable_carriers.Store`."
    )

    _add_missing_carriers_from_costs(n, costs, ["NH3"])

    buses_i = n.buses.index[n.buses.carrier == "AC"]
    h2_buses_i = buses_i + " H2"
    bus_sub_dict = {
        k: n.buses.loc[buses_i, k].values for k in ["x", "y", "country"]
    }

    # Verify H2 buses exist
    missing_h2 = h2_buses_i.difference(n.buses.index)
    if not missing_h2.empty:
        logger.warning(
            "Skipping NH3 attachment because hydrogen buses are missing. "
            "Ensure H2 is in extendable_carriers.Store and runs before NH3."
        )
        return

    # --- NH3 buses ---
    nh3_buses_i = n.madd(
        "Bus", buses_i + " NH3", carrier="NH3", **bus_sub_dict
    )

    # --- NH3 stores ---
    max_hours_nh3 = elec_opts.get("max_hours", {}).get("NH3", 168)
    n.madd(
        "Store",
        nh3_buses_i,
        bus=nh3_buses_i,
        carrier="NH3",
        e_nom_extendable=True,
        e_cyclic=True,
        capital_cost=costs.at["ammonia storage", "capital_cost"],
    )

    # --- NH3 synthesis links (H2 → NH3, consuming electricity) ---
    # DEA recipe: 1.13472 H2 + 0.16 el → 1.0 NH3
    nh3_synthesis_eff = costs.at["ammonia synthesis", "efficiency"]  # ≈ 0.881
    elec_per_h2 = 0.16 / 1.13472  # ≈ 0.141

    n.madd(
        "Link",
        nh3_buses_i + " NH3 synthesis",
        bus0=h2_buses_i,
        bus1=nh3_buses_i,
        bus2=buses_i,  # electricity drawn
        carrier="NH3 synthesis",
        p_nom_extendable=True,
        efficiency=nh3_synthesis_eff,
        efficiency2=-elec_per_h2,  # negative = consumed
        # Capital cost on bus0 (H2 input) basis
        capital_cost=costs.at["ammonia synthesis", "capital_cost"]
        * nh3_synthesis_eff,
        marginal_cost=costs.at["ammonia synthesis", "marginal_cost"],
        # Haber-Bosch operational constraints
        p_min_pu=0.3,
        ramp_limit_up=0.1,
        ramp_limit_down=0.1,
    )

    logger.info(
        f"Added {len(nh3_buses_i)} NH3 buses, stores and synthesis links "
        f"(eff={nh3_synthesis_eff:.3f}, elec_draw={elec_per_h2:.3f}/MWh_H2, "
        f"p_min_pu=0.3, ramp=0.1)"
    )


def attach_ammonia_ccgt(n, costs, config):
    """Add CCGT NH3 links (NH3 bus → AC bus) at every node with an NH3 bus."""
    elec_opts = config["electricity"]
    ext_carriers = elec_opts["extendable_carriers"]
    as_links = ext_carriers.get("Link", [])
    as_stores = ext_carriers.get("Store", [])

    if "CCGT NH3" not in as_links:
        return

    assert "NH3" in as_stores, (
        "Attaching CCGT NH3 requires ammonia storage to be modelled "
        "as Store-Link-Bus combination. Add 'NH3' to "
        "`electricity.extendable_carriers.Store`."
    )

    _add_missing_carriers_from_costs(n, costs, ["CCGT NH3"])

    buses_i = n.buses.index[n.buses.carrier == "AC"]
    nh3_buses_i = buses_i + " NH3"

    missing_nh3 = nh3_buses_i.difference(n.buses.index)
    if not missing_nh3.empty:
        logger.warning(
            "Skipping CCGT NH3 — NH3 buses missing. "
            "Ensure NH3 is in extendable_carriers.Store."
        )
        return

    n.madd(
        "Link",
        nh3_buses_i + " CCGT NH3",
        bus0=nh3_buses_i,
        bus1=buses_i,
        carrier="CCGT NH3",
        p_nom_extendable=True,
        efficiency=costs.at["CCGT NH3", "efficiency"],
        capital_cost=costs.at["CCGT NH3", "capital_cost"]
        * costs.at["CCGT NH3", "efficiency"],
        marginal_cost=costs.at["CCGT NH3", "marginal_cost"],
    )

    logger.info(f"Added {len(buses_i)} CCGT NH3 links")


def attach_ammonia_pipelines(n, costs, config, transmission_efficiency):
    """Add NH3 pipeline links between nodes, mirroring the H2 pipeline pattern."""
    elec_opts = config["electricity"]
    ext_carriers = elec_opts["extendable_carriers"]
    as_stores = ext_carriers.get("Store", [])

    if "NH3 pipeline" not in ext_carriers.get("Link", []):
        return

    assert "NH3" in as_stores, (
        "Attaching NH3 pipelines requires ammonia storage to be modelled "
        "as Store-Link-Bus combination. Add 'NH3' to "
        "`electricity.extendable_carriers.Store`."
    )

    # Determine bus pairs from existing lines/DC links
    ln_attrs = ["bus0", "bus1", "length"]
    lk_attrs = ["bus0", "bus1", "length", "underwater_fraction"]
    ac_bus_set = set(n.buses.index[n.buses.carrier == "AC"])
    candidates = pd.concat(
        [n.lines[ln_attrs], n.links.query('carrier=="DC"')[lk_attrs]]
    ).fillna(0).reset_index(drop=True)
    # Filter to only include bus pairs where BOTH endpoints exist as AC buses.
    # After simplify/cluster, n.lines may reference buses that were merged away;
    # pipelines to non-existent buses create orphaned links that break bus
    # balance constraints and produce spurious flows.
    candidates = candidates[
        candidates.bus0.isin(ac_bus_set) & candidates.bus1.isin(ac_bus_set)
    ].reset_index(drop=True)

    nh3_links = candidates[
        ~pd.DataFrame(np.sort(candidates[["bus0", "bus1"]])).duplicated()
    ]
    nh3_links.index = nh3_links.apply(
        lambda c: f"NH3 pipeline {c.bus0}-{c.bus1}", axis=1
    )

    # Apply submarine cost factor: underwater portions cost more than onshore
    submarine_factor = elec_opts.get("pipeline_submarine_cost_factor", 1.0)
    base_cost_per_km = costs.at["NH3 pipeline", "capital_cost"]
    capital_cost = (
        base_cost_per_km
        * nh3_links.length
        * (1 + nh3_links.underwater_fraction * (submarine_factor - 1))
    )

    n.madd(
        "Link",
        nh3_links.index,
        bus0=nh3_links.bus0.values + " NH3",
        bus1=nh3_links.bus1.values + " NH3",
        p_min_pu=-1,
        p_nom_extendable=True,
        length=nh3_links.length.values,
        capital_cost=capital_cost,
        carrier="NH3 pipeline",
    )

    # Split into bidirectional links with transmission losses
    lossy_bidirectional_links(n, "NH3 pipeline")
    set_length_based_efficiency(n, "NH3 pipeline", " NH3", transmission_efficiency)

    logger.info(f"Added {len(nh3_links)} NH3 pipeline links (bidirectional)")


def attach_hydrogen_pipelines(n, costs, config, transmission_efficiency):
    elec_opts = config["electricity"]
    ext_carriers = elec_opts["extendable_carriers"]
    as_stores = ext_carriers.get("Store", [])

    if "H2 pipeline" not in ext_carriers.get("Link", []):
        return

    assert "H2" in as_stores, (
        "Attaching hydrogen pipelines requires hydrogen "
        "storage to be modelled as Store-Link-Bus combination. See "
        "`config.yaml` at `electricity: extendable_carriers: Store:`."
    )

    # determine bus pairs
    ln_attrs = ["bus0", "bus1", "length"]
    lk_attrs = ["bus0", "bus1", "length", "underwater_fraction"]
    ac_bus_set = set(n.buses.index[n.buses.carrier == "AC"])
    candidates = pd.concat(
        [n.lines[ln_attrs], n.links.query('carrier=="DC"')[lk_attrs]]
    ).fillna(0).reset_index(drop=True)
    # Filter to only include bus pairs where BOTH endpoints exist as AC buses.
    # After simplify/cluster, n.lines may reference buses that were merged away;
    # pipelines to non-existent buses create orphaned links that break bus
    # balance constraints and produce spurious flows.
    candidates = candidates[
        candidates.bus0.isin(ac_bus_set) & candidates.bus1.isin(ac_bus_set)
    ].reset_index(drop=True)

    # remove bus pair duplicates regardless of order of bus0 and bus1
    h2_links = candidates[
        ~pd.DataFrame(np.sort(candidates[["bus0", "bus1"]])).duplicated()
    ]
    h2_links.index = h2_links.apply(lambda c: f"H2 pipeline {c.bus0}-{c.bus1}", axis=1)

    # Apply submarine cost factor: underwater portions cost more than onshore
    submarine_factor = elec_opts.get("pipeline_submarine_cost_factor", 1.0)
    base_cost_per_km = costs.at["H2 pipeline", "capital_cost"]
    capital_cost = (
        base_cost_per_km
        * h2_links.length
        * (1 + h2_links.underwater_fraction * (submarine_factor - 1))
    )

    # add pipelines
    n.madd(
        "Link",
        h2_links.index,
        bus0=h2_links.bus0.values + " H2",
        bus1=h2_links.bus1.values + " H2",
        p_min_pu=-1,
        p_nom_extendable=True,
        length=h2_links.length.values,
        capital_cost=capital_cost,
        carrier="H2 pipeline",
    )

    # split the pipeline into two unidirectional links to properly apply transmission losses in both directions.
    lossy_bidirectional_links(n, "H2 pipeline")

    # set the pipelines efficiency and the electricity required by the pipeline for compression
    set_length_based_efficiency(n, "H2 pipeline", " H2", transmission_efficiency)


def attach_hydrogen_ccgt(n, costs, config):
    elec_opts = config["electricity"]
    ext_carriers = elec_opts["extendable_carriers"]
    as_links = ext_carriers.get("Link", [])
    as_stores = ext_carriers.get("Store", [])

    if not any(carrier in as_links for carrier in ["CCGT H2", "H2 CCGT"]):
        return

    assert "H2" in as_stores, (
        "Attaching hydrogen CCGT requires hydrogen "
        "storage to be modelled as Store-Link-Bus combination. See "
        "`config.yaml` at `electricity: extendable_carriers: Store:`."
    )

    _add_missing_carriers_from_costs(n, costs, ["CCGT H2"])

    buses_i = n.buses.index[n.buses.carrier == "AC"]
    h2_buses_i = buses_i + " H2"

    missing_h2_buses = h2_buses_i.difference(n.buses.index)
    if not missing_h2_buses.empty:
        logger.warning(
            "Skipping CCGT H2 attachment because hydrogen buses are missing. "
            "Ensure `H2` is included in `electricity.extendable_carriers.Store`."
        )
        return

    n.madd(
        "Link",
        h2_buses_i + " CCGT H2",
        bus0=h2_buses_i,
        bus1=buses_i,
        carrier="CCGT H2",
        p_nom_extendable=True,
        efficiency=costs.at["CCGT H2", "efficiency"],
        # Link capacity is defined on bus0; convert from electrical-output CAPEX.
        capital_cost=costs.at["CCGT H2", "capital_cost"]
        * costs.at["CCGT H2", "efficiency"],
        marginal_cost=costs.at["CCGT H2", "marginal_cost"],
    )


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake("add_extra_components", simpl="", clusters=10)

    configure_logging(snakemake)

    n = pypsa.Network(snakemake.input.network)
    Nyears = n.snapshot_weightings.objective.sum() / 8760.0
    transmission_efficiency = snakemake.params.transmission_efficiency
    config = snakemake.config

    costs = load_costs(
        snakemake.input.tech_costs,
        config["costs"],
        config["electricity"],
        Nyears,
    )

    attach_storageunits(n, costs, config)
    attach_stores(n, costs, config)
    attach_hydrogen_ccgt(n, costs, config)
    attach_hydrogen_pipelines(n, costs, config, transmission_efficiency)
    attach_ammonia_stores(n, costs, config)
    attach_ammonia_ccgt(n, costs, config)
    attach_ammonia_pipelines(n, costs, config, transmission_efficiency)

    add_nice_carrier_names(n, config=snakemake.config)

    n.meta = dict(snakemake.config, **dict(wildcards=dict(snakemake.wildcards)))
    n.export_to_netcdf(snakemake.output[0])

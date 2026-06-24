"""Prepare collaborator asset tables and propose substation connections."""

rule prepare_energy_assets:
    input:
        workbook=f"{INCOMING_ENERGY}/power_demand/Power Demand.xlsx",
        substations=f"{INCOMING_ENERGY}/substation/Substation.shp",
        routes=f"{INCOMING_ENERGY}/power_transmission/PowerGrid.shp",
        generation_points=f"{INCOMING_ENERGY}/generation_source/GenSource1.shp",
        generation_areas=f"{INCOMING_ENERGY}/generation_source/GenSource2.shp",
    output:
        substations=f"{PROCESSED_ENERGY}/substations.parquet",
        routes=f"{PROCESSED_ENERGY}/transmission_routes.parquet",
        register=f"{PROCESSED_ENERGY}/generation_register_template.csv",
        demand=f"{PROCESSED_ENERGY}/annual_sector_demand_gwh.csv",
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli prepare-assets \
          --input-dir {INCOMING_ENERGY} \
          --output-dir {PROCESSED_ENERGY}
        """


rule build_energy_topology:
    input:
        substations=rules.prepare_energy_assets.output.substations,
        routes=rules.prepare_energy_assets.output.routes,
    output:
        buses=f"{TOPOLOGY_DIR}/buses.parquet",
        lines=f"{TOPOLOGY_DIR}/lines.parquet",
        report=f"{TOPOLOGY_DIR}/topology_report.json",
    params:
        snap_tolerance=config["energy"]["topology"]["snap_tolerance_m"],
        voltage=config["energy"]["topology"]["default_voltage_kv"],
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli build-topology \
          --processed-dir {PROCESSED_ENERGY} \
          --output-dir {TOPOLOGY_DIR} \
          --snap-tolerance-m {params.snap_tolerance} \
          --default-voltage-kv {params.voltage}
        """

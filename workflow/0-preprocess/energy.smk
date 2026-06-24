"""Prepare collaborator asset tables without deriving network connections."""

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

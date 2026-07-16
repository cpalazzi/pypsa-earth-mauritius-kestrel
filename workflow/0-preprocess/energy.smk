"""Prepare provided assets and human-readable network input templates."""

rule prepare_energy_assets:
    input:
        workbook=f"{INCOMING_ENERGY}/power_demand/Power Demand.xlsx",
        substations=f"{INCOMING_ENERGY}/substation/Substation.shp",
        routes=f"{INCOMING_ENERGY}/power_transmission/PowerGrid.shp",
        generation_points=f"{INCOMING_ENERGY}/generation_source/GenSource1.shp",
        generation_areas=f"{INCOMING_ENERGY}/generation_source/GenSource2.shp",
    output:
        substations=f"{PROCESSED_ENERGY}/substations.parquet",
        snapped_substations=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        snap_distances=f"{PROCESSED_ENERGY}/substation_snap_distances.csv",
        routes=f"{PROCESSED_ENERGY}/transmission_routes.parquet",
        generators=f"{PROCESSED_ENERGY}/generators.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
        generator_template=f"{TEMPLATES_ENERGY}/generators.csv",
        line_template=f"{TEMPLATES_ENERGY}/lines.csv",
        demand=f"{PROCESSED_ENERGY}/annual_sector_demand_gwh.csv",
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli prepare-assets \
          --input-dir {INCOMING_ENERGY} \
          --output-dir {PROCESSED_ENERGY}
        """

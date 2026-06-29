"""Electricity supply calculations during asset outages."""

rule run_energy_baseline:
    input:
        buses=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        lines=f"{PROCESSED_ENERGY}/existing_lines.csv",
        generators=f"{PROCESSED_ENERGY}/existing_generators.csv",
        demand=f"{PROCESSED_ENERGY}/demand_profile.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        summary=f"{OUTPUT_ENERGY}/summary_metrics.csv",
        metrics=f"{OUTPUT_ENERGY}/baseline_metrics.json",
        unserved=f"{OUTPUT_ENERGY}/baseline_unserved_energy_mwh_by_substation.csv",
        network=f"{OUTPUT_ENERGY}/baseline_network.nc",
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=OUTPUT_ENERGY,
        solver=ENERGY_SOLVER,
        value_of_lost_load=VALUE_OF_LOST_LOAD,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli run-interruptions \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir} \
          --solver {params.solver} \
          --value-of-lost-load {params.value_of_lost_load}
        """

rule run_energy_outage:
    input:
        buses=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        lines=f"{PROCESSED_ENERGY}/existing_lines.csv",
        generators=f"{PROCESSED_ENERGY}/existing_generators.csv",
        demand=f"{PROCESSED_ENERGY}/demand_profile.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
        disruptions=f"{PROCESSED_ENERGY}/disruptions.csv",
    output:
        outage_metrics=f"{OUTPUT_ENERGY}/outage_metrics.json",
        outage_unserved=f"{OUTPUT_ENERGY}/outage_unserved_energy_mwh_by_substation.csv",
        outage_network=f"{OUTPUT_ENERGY}/outage_network.nc",
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=OUTPUT_ENERGY,
        solver=ENERGY_SOLVER,
        value_of_lost_load=VALUE_OF_LOST_LOAD,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli run-interruptions \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir} \
          --solver {params.solver} \
          --value-of-lost-load {params.value_of_lost_load} \
          --disruptions {input.disruptions}
        """

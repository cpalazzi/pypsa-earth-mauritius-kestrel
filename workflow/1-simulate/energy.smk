"""Electricity supply calculations during asset outages.

This stage cannot build new assets. It will be enabled once maximum line power,
power-station output, connected substations and demand over time are complete.
"""

rule validate_energy_model_inputs:
    input:
        lines=f"{PROCESSED_ENERGY}/existing_lines.csv",
        generators=f"{PROCESSED_ENERGY}/existing_generators.csv",
        demand=f"{PROCESSED_ENERGY}/demand_profile.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        f"{OUTPUT_ENERGY}/input_validation.txt",
    shell:
        """
        mkdir -p $(dirname {output})
        printf '%s\n' \
          'Input files exist. Run the asset-model notebook to check line limits, power-station data and substation assignments.' \
          > {output}
        """

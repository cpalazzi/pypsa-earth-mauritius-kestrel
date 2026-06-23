"""Operational interruption simulations.

This stage intentionally has no capacity-expansion rule. A simulation rule will
be enabled once CEB line ratings, generator capacities, generator-to-bus
assignments and a calibrated demand profile are complete.
"""

rule validate_energy_model_inputs:
    input:
        topology=f"{TOPOLOGY_DIR}/topology_report.json",
        generators=f"{PROCESSED_ENERGY}/existing_generators.csv",
        demand=f"{PROCESSED_ENERGY}/demand_profile.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        f"{OUTPUT_ENERGY}/input_validation.txt",
    shell:
        """
        mkdir -p $(dirname {output})
        printf '%s\n' \
          'Input files exist. Run the asset-model notebook to validate ratings, capacities and assignments.' \
          > {output}
        """

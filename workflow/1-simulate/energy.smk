"""Operational interruption simulations.

This stage intentionally has no capacity-expansion rule. A simulation rule will
be enabled once CEB line ratings, generator capacities, generator-to-bus
assignments and a calibrated demand profile are complete.
"""


rule validate_energy_model_inputs:
    input:
        topology=f"{config['energy']['topology_dir']}/topology_report.json",
        generators=f"{config['energy']['processed_dir']}/existing_generators.csv",
        demand=f"{config['energy']['processed_dir']}/demand_profile.csv",
        service_weights=f"{config['energy']['processed_dir']}/service_weights.csv",
    output:
        "data/out/energy/input_validation.txt",
    shell:
        """
        mkdir -p $(dirname {output})
        printf '%s\n' \
          'Input files exist. Run the asset-model notebook to validate ratings, capacities and assignments.' \
          > {output}
        """

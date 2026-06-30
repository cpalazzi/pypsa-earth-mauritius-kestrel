"""Electricity supply calculations during asset outages."""

rule build_base_network:
    input:
        buses=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        lines=f"{PROCESSED_ENERGY}/lines.csv",
        generators=f"{PROCESSED_ENERGY}/generators.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        network=f"{NETWORKS_ENERGY}/base.nc",
        metadata=f"{NETWORKS_ENERGY}/base_metadata.json",
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=NETWORKS_ENERGY,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli build-network base \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir}
        """

rule build_inferred_network:
    input:
        buses=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        network=f"{NETWORKS_ENERGY}/inferred.nc",
        metadata=f"{NETWORKS_ENERGY}/inferred_metadata.json",
        nodes=f"{NETWORKS_ENERGY}/inferred_distribution/inferred_distribution_nodes.csv",
        edges=f"{NETWORKS_ENERGY}/inferred_distribution/inferred_distribution_edges.csv",
        service_weights=f"{NETWORKS_ENERGY}/inferred_distribution/service_weights.csv",
        graph_metadata=(
            f"{NETWORKS_ENERGY}/inferred_distribution/"
            "inferred_distribution_metadata.json"
        ),
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=NETWORKS_ENERGY,
        region=INFERRED_NETWORK_REGION,
        network_type=INFERRED_NETWORK_TYPE,
        max_anchor_distance_m=1000,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli build-network inferred \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir} \
          --output-name inferred \
          --overwrite \
          --region {params.region} \
          --network-type {params.network_type} \
          --max-anchor-distance-m {params.max_anchor_distance_m}
        """

rule run_energy_baseline:
    input:
        network=f"{NETWORKS_ENERGY}/base.nc",
        demand=f"{PROCESSED_ENERGY}/demand_profile.csv",
        service_weights=f"{PROCESSED_ENERGY}/service_weights.csv",
    output:
        demand_summary=f"{OUTPUT_ENERGY}/demand_summary.csv",
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
          --network {input.network} \
          --solver {params.solver} \
          --value-of-lost-load {params.value_of_lost_load}
        """

rule run_energy_outage:
    input:
        network=f"{NETWORKS_ENERGY}/base.nc",
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
          --network {input.network} \
          --solver {params.solver} \
          --value-of-lost-load {params.value_of_lost_load} \
          --disruptions {input.disruptions}
        """

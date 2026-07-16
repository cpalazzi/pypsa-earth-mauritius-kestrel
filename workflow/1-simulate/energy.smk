"""Electricity supply calculations during asset outages."""

rule build_base_network:
    input:
        buses=f"{PROCESSED_ENERGY}/snapped_substations.parquet",
        routes=f"{PROCESSED_ENERGY}/transmission_routes.parquet",
        generators=f"{PROCESSED_ENERGY}/generators.csv",
    output:
        network=f"{NETWORKS_ENERGY}/base.nc",
        metadata=f"{NETWORKS_ENERGY}/base_metadata.json",
        generators=f"{OUTPUT_ENERGY}/base/generators.csv",
        lines=f"{OUTPUT_ENERGY}/base/lines.csv",
        validation=f"{OUTPUT_ENERGY}/base/validation.json",
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=NETWORKS_ENERGY,
        export_root=OUTPUT_ENERGY,
        reference_line_length_km=CEB_LINE_LENGTH_KM,
        line_length_tolerance=LINE_LENGTH_TOLERANCE,
        reference_generation_capacity_mw=CEB_GENERATION_CAPACITY_MW,
        generation_capacity_tolerance=GENERATION_CAPACITY_TOLERANCE,
        route_gap_tolerance_m=BASE_ROUTE_GAP_TOLERANCE_M,
        default_voltage_kv=BASE_DEFAULT_VOLTAGE_KV,
        topology_capacity_mva=BASE_TOPOLOGY_CAPACITY_MVA,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli build-network base \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir} \
          --export-root {params.export_root} \
          --overwrite \
          --reference-line-length-km {params.reference_line_length_km} \
          --line-length-tolerance-fraction {params.line_length_tolerance} \
          --reference-generation-capacity-mw {params.reference_generation_capacity_mw} \
          --generation-capacity-tolerance-fraction {params.generation_capacity_tolerance} \
          --base-route-gap-tolerance-m {params.route_gap_tolerance_m} \
          --base-default-voltage-kv {params.default_voltage_kv} \
          --base-topology-capacity-mva {params.topology_capacity_mva}
        """

rule build_inferred_network:
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
        generators=f"{OUTPUT_ENERGY}/inferred/generators.csv",
        lines=f"{OUTPUT_ENERGY}/inferred/lines.csv",
        validation=f"{OUTPUT_ENERGY}/inferred/validation.json",
    params:
        input_dir=PROCESSED_ENERGY,
        output_dir=NETWORKS_ENERGY,
        export_root=OUTPUT_ENERGY,
        region=INFERRED_NETWORK_REGION,
        network_type=INFERRED_NETWORK_TYPE,
        max_anchor_distance_m=1000,
        line_length_tolerance=LINE_LENGTH_TOLERANCE,
    shell:
        """
        .venv/bin/python -m mu_star_energy.cli build-network inferred \
          --input-dir {params.input_dir} \
          --output-dir {params.output_dir} \
          --export-root {params.export_root} \
          --output-name inferred \
          --overwrite \
          --region {params.region} \
          --network-type {params.network_type} \
          --max-anchor-distance-m {params.max_anchor_distance_m} \
          --line-length-tolerance-fraction {params.line_length_tolerance}
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

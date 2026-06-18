import pandas as pd

from mu_star_energy.damage import damage_to_disruptions


def test_damage_to_disruptions():
    result = damage_to_disruptions(
        pd.DataFrame(
            {
                "component": ["Line", "Generator"],
                "asset_id": ["L1", "G1"],
                "damage_fraction": [1.0, 0.25],
            }
        )
    )

    assert result["available_fraction"].tolist() == [0.0, 0.75]


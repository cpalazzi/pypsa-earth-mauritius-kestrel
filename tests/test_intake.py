import pytest

from mu_star_energy.intake import validate_collaborator_inputs


def test_collaborator_input_check_lists_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        validate_collaborator_inputs(tmp_path)

    message = str(error.value)
    assert str(tmp_path) in message
    assert "power_demand/Power Demand.xlsx" in message
    assert "data/0-incoming/energy/collaborator" in message

import pytest
from users import get_user_profile

def test_get_user_profile_name_error() -> None:
    # Assert that accessing a profile raises NameError due to the bug
    with pytest.raises(NameError) as exc_info:
        get_user_profile(1)
    assert "profile_db" in str(exc_info.value)

def test_get_user_profile_invalid_id() -> None:
    # Assert that negative IDs raise ValueError
    with pytest.raises(ValueError) as exc_info:
        get_user_profile(-1)
    assert "Invalid user_id" in str(exc_info.value)

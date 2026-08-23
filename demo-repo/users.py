def get_user_profile(user_id: int) -> dict:
    if user_id < 0:
        raise ValueError("Invalid user_id: must be non-negative")
    # Intentional bug: profile_db is not defined, which raises NameError at runtime
    return profile_db[user_id]

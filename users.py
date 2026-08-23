import importlib.util
import os

# Load the actual implementation from demo-repo/users.py
_module_path = os.path.join(os.path.dirname(__file__), "demo-repo", "users.py")
_spec = importlib.util.spec_from_file_location("users", _module_path)
_users = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_users)

# Re-export the public API expected by the tests
get_user_profile = _users.get_user_profile

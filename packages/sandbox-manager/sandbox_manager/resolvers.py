import os
import sys
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class EcosystemAdapter(ABC):
    """
    Abstract interface for repository language/ecosystem adapters.
    Responsible for test command detection and dependency command generation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the ecosystem (e.g. 'python')."""
        pass

    @abstractmethod
    def matches(self, workspace_path: str) -> bool:
        """Determines if the workspace belongs to this ecosystem."""
        pass

    @abstractmethod
    def resolve_test_command(self, workspace_path: str, explicit_command: Optional[str] = None) -> str:
        """Resolves the command line used to execute tests."""
        pass

    @abstractmethod
    def get_dependency_install_commands(self, workspace_path: str, in_container: bool = True) -> List[str]:
        """Returns list of dependency preparation commands."""
        pass


class PythonAdapter(EcosystemAdapter):
    """
    Python ecosystem adapter.
    Inspects standard metadata: requirements.txt, pyproject.toml, setup.py, setup.cfg, pytest.ini.
    """

    @property
    def name(self) -> str:
        return "python"

    def matches(self, workspace_path: str) -> bool:
        if not os.path.exists(workspace_path):
            return False

        python_indicators = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
            "poetry.lock",
            "pytest.ini",
            "tox.ini"
        ]
        for indicator in python_indicators:
            if os.path.exists(os.path.join(workspace_path, indicator)):
                return True

        # Scan for any .py files in root or src/tests
        for root, dirs, files in os.walk(workspace_path):
            # Skip hidden and git directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if any(f.endswith(".py") for f in files):
                return True
            # Limit depth of search
            rel_depth = os.path.relpath(root, workspace_path).count(os.sep)
            if rel_depth >= 2:
                dirs.clear()

        return False

    def resolve_test_command(self, workspace_path: str, explicit_command: Optional[str] = None) -> str:
        # 1. If an explicit custom command is configured and it's not the generic default or empty, honor it
        if explicit_command and explicit_command.strip() and explicit_command.strip() != "pytest":
            return explicit_command.strip()

        # 2. Inspect project metadata for test runner declaration
        pyproject_path = os.path.join(workspace_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "[tool.pytest" in content or "pytest" in content:
                        return "pytest"
            except Exception:
                pass

        pytest_ini = os.path.join(workspace_path, "pytest.ini")
        if os.path.exists(pytest_ini):
            return "pytest"

        setup_cfg = os.path.join(workspace_path, "setup.cfg")
        if os.path.exists(setup_cfg):
            try:
                with open(setup_cfg, "r", encoding="utf-8", errors="ignore") as f:
                    if "[tool:pytest]" in f.read():
                        return "pytest"
            except Exception:
                pass

        # 3. Check for tests folder or test files
        tests_dir = os.path.join(workspace_path, "tests")
        test_dir = os.path.join(workspace_path, "test")
        has_test_files = False
        if os.path.isdir(tests_dir) or os.path.isdir(test_dir):
            has_test_files = True
        else:
            try:
                has_test_files = any(
                    (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py")
                    for f in os.listdir(workspace_path)
                    if os.path.isfile(os.path.join(workspace_path, f))
                )
            except Exception:
                pass

        if has_test_files:
            return "pytest"

        # If explicit_command was given as 'pytest', return it
        if explicit_command:
            return explicit_command

        # Default fallback for python
        return "pytest"

    def get_dependency_install_commands(self, workspace_path: str, in_container: bool = True) -> List[str]:
        commands: List[str] = []
        py_exec = "python" if in_container else f'"{sys.executable}"'

        req_path = os.path.join(workspace_path, "requirements.txt")
        pyproject_path = os.path.join(workspace_path, "pyproject.toml")
        setup_path = os.path.join(workspace_path, "setup.py")

        deps_dir = os.path.join(workspace_path, ".deps")
        if os.path.exists(req_path):
            if in_container:
                commands.append(f"{py_exec} -m pip install --no-cache-dir -r requirements.txt")
            else:
                commands.append(f'{py_exec} -m pip install --quiet --target "{deps_dir}" -r requirements.txt')
        elif os.path.exists(pyproject_path):
            if in_container:
                commands.append(f"{py_exec} -m pip install --no-cache-dir .")
            else:
                commands.append(f'{py_exec} -m pip install --quiet --target "{deps_dir}" .')
        elif os.path.exists(setup_path):
            if in_container:
                commands.append(f"{py_exec} -m pip install --no-cache-dir -e .")
            else:
                commands.append(f'{py_exec} -m pip install --quiet --target "{deps_dir}" .')

        return commands


class TestCommandResolver:
    """
    Registry of ecosystem adapters.
    Resolves test commands and dependencies generically across supported ecosystems.
    """
    __test__ = False

    def __init__(self, adapters: Optional[List[EcosystemAdapter]] = None):
        self.adapters = adapters or [PythonAdapter()]

    def resolve(self, workspace_path: str, explicit_command: Optional[str] = None) -> Tuple[str, Optional[EcosystemAdapter]]:
        """
        Finds matching adapter and resolves the test command.
        """
        for adapter in self.adapters:
            if adapter.matches(workspace_path):
                cmd = adapter.resolve_test_command(workspace_path, explicit_command=explicit_command)
                return cmd, adapter

        # Fallback if no specific ecosystem matches
        fallback_cmd = explicit_command if explicit_command else "pytest"
        return fallback_cmd, None

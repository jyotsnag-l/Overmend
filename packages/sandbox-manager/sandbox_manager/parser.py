import re
from typing import Dict, Optional, Tuple


class TestOutputParser:
    """
    Parses test runner output into structured test metrics:
    - tests_total
    - tests_passed
    - tests_failed
    - tests_skipped

    Guarantees:
    - Never invents counts when parsing is unreliable or unrecognized.
    - Preserves raw output.
    """
    __test__ = False

    @classmethod
    def parse(cls, test_command: str, stdout: str, stderr: str) -> Dict[str, Optional[int]]:
        result: Dict[str, Optional[int]] = {
            "tests_total": None,
            "tests_passed": None,
            "tests_failed": None,
            "tests_skipped": None,
        }

        full_output = f"{stdout}\n{stderr}"
        if not full_output.strip():
            return result

        cmd_lower = test_command.lower()
        if "pytest" in cmd_lower:
            parsed = cls._parse_pytest(full_output)
            if parsed:
                result.update(parsed)
                return result

        if "unittest" in cmd_lower or "python -m unittest" in cmd_lower:
            parsed = cls._parse_unittest(full_output)
            if parsed:
                result.update(parsed)
                return result

        # Generic attempt: try pytest parsing first, then unittest
        parsed = cls._parse_pytest(full_output)
        if parsed and parsed.get("tests_total") is not None:
            result.update(parsed)
            return result

        parsed = cls._parse_unittest(full_output)
        if parsed and parsed.get("tests_total") is not None:
            result.update(parsed)
            return result

        return result

    @classmethod
    def _parse_pytest(cls, output: str) -> Optional[Dict[str, Optional[int]]]:
        """
        Parses standard pytest summary lines, e.g.:
        '=== 2 passed in 0.04s ==='
        '=== 1 failed, 2 passed, 1 skipped in 0.12s ==='
        '=== 1 error in 0.05s ==='
        """
        # Look for summary lines bounded by '='
        lines = output.splitlines()
        for line in reversed(lines):
            line_str = line.strip()
            if not line_str.startswith("=") or not line_str.endswith("="):
                continue

            # Check if this line looks like a pytest completion summary
            if any(k in line_str for k in ["passed", "failed", "error", "skipped", "no tests ran"]):
                passed = 0
                failed = 0
                skipped = 0
                found_any = False

                m_pass = re.search(r"(\d+)\s+passed", line_str)
                if m_pass:
                    passed = int(m_pass.group(1))
                    found_any = True

                m_fail = re.search(r"(\d+)\s+failed", line_str)
                if m_fail:
                    failed += int(m_fail.group(1))
                    found_any = True

                m_err = re.search(r"(\d+)\s+error", line_str)
                if m_err:
                    failed += int(m_err.group(1))
                    found_any = True

                m_skip = re.search(r"(\d+)\s+skipped", line_str)
                if m_skip:
                    skipped = int(m_skip.group(1))
                    found_any = True

                if found_any:
                    total = passed + failed + skipped
                    return {
                        "tests_total": total,
                        "tests_passed": passed,
                        "tests_failed": failed,
                        "tests_skipped": skipped,
                    }

        return None

    @classmethod
    def _parse_unittest(cls, output: str) -> Optional[Dict[str, Optional[int]]]:
        """
        Parses standard unittest output, e.g.:
        'Ran 5 tests in 0.002s'
        'OK' or 'OK (skipped=1)'
        'FAILED (failures=1, errors=1)'
        """
        ran_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
        if not ran_match:
            return None

        total = int(ran_match.group(1))
        failed = 0
        skipped = 0

        fail_match = re.search(r"FAILED\s*\((.*?)\)", output)
        if fail_match:
            details = fail_match.group(1)
            m_f = re.search(r"failures=(\d+)", details)
            if m_f:
                failed += int(m_f.group(1))
            m_e = re.search(r"errors=(\d+)", details)
            if m_e:
                failed += int(m_e.group(1))
            m_s = re.search(r"skipped=(\d+)", details)
            if m_s:
                skipped += int(m_s.group(1))
        else:
            ok_match = re.search(r"OK\s*(?:\((.*?)\))?", output)
            if ok_match and ok_match.group(1):
                details = ok_match.group(1)
                m_s = re.search(r"skipped=(\d+)", details)
                if m_s:
                    skipped = int(m_s.group(1))

        passed = max(0, total - failed - skipped)
        return {
            "tests_total": total,
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_skipped": skipped,
        }

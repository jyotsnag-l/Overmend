import re
from typing import Dict, List

def parse_patch_diff(patch_diff: str) -> Dict[str, List[int]]:
    """
    Parses a unified diff to find modified files and the line numbers that were changed/added.
    
    Returns:
        Dict[str, List[int]]: A mapping of file path (relative to repo root) to a list of 1-indexed line numbers.
    """
    lines = patch_diff.splitlines()
    modified_files: Dict[str, List[int]] = {}
    current_file: str = None
    current_line = 0

    for line in lines:
        if line.startswith("--- "):
            continue
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
            modified_files[current_file] = []
        elif line.startswith("@@"):
            # Format: @@ -old_start,old_count +new_start,new_count @@
            match = re.match(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@", line)
            if match and current_file:
                current_line = int(match.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file is not None:
                modified_files[current_file].append(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Deletions do not increment the line counter in the new file
            continue
        else:
            # Context line
            current_line += 1

    # Filter out empty file modifications
    return {k: sorted(list(set(v))) for k, v in modified_files.items() if v}

from unidiff import PatchSet

valid_diff = (
    "diff --git a/app.py b/app.py\n"
    "--- a/app.py\n"
    "+++ b/app.py\n"
    "@@ -1,2 +1,4 @@\n"
    " def div(x):\n"
    "-    return x / 0\n"
    "+    if x == 0:\n"
    "+        return 0\n"
    "+    return x / x\n"
)

patch_set = PatchSet(valid_diff.splitlines(keepends=True))
print("Files changed:", len(patch_set))
for patched_file in patch_set:
    print("File path:", patched_file.path)
    for hunk in patched_file:
        print("Hunk:", hunk)
        print("Hunk added count:", hunk.added)
        print("Hunk removed count:", hunk.removed)
        for line in hunk:
            print(f"Line: {repr(line.line_type)}: {repr(line.value)}")

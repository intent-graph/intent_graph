#!/usr/bin/env python3
"""Filter unwanted paths from DOC_MANIFEST YAML files."""

import re
from pathlib import Path

# Directory patterns to exclude (will match anywhere in path)
EXCLUDE_PATTERNS = [
    "_implementation__LEGACY",
    "t1_distill",
]


def should_exclude_path(path: str) -> bool:
    """Check if a path contains any excluded pattern."""
    return any(pattern in path for pattern in EXCLUDE_PATTERNS)


def get_indent_level(line: str) -> int:
    """Get the indentation level of a line (number of leading spaces)."""
    return len(line) - len(line.lstrip())


def filter_sections_yaml(input_path: Path, output_path: Path):
    """Filter sections YAML file, excluding entire directory trees."""
    with open(input_path) as f:
        lines = f.readlines()

    filtered_lines = []
    skip_until_indent = None  # When set, skip lines until we see this indent level or less
    excluded_files = 0
    total_files = 0

    for i, line in enumerate(lines):
        # Handle first line (stats) - we'll update it later
        if i == 0:
            filtered_lines.append(line)  # Placeholder, will update
            continue

        # Get current indentation
        indent = get_indent_level(line)

        # If we're skipping, check if we can resume
        if skip_until_indent is not None:
            if indent <= skip_until_indent:
                skip_until_indent = None  # Resume processing
            else:
                continue  # Still skipping

        # Check if this line defines a path (ends with /:  or .md:)
        stripped = line.lstrip()
        if stripped.endswith("/:") or (stripped.endswith(":") and ".md" in stripped):
            path_part = stripped.rstrip(":").strip()

            # Check if this path should be excluded
            if should_exclude_path(path_part):
                excluded_files += 1
                skip_until_indent = indent  # Skip all content at deeper indentation
                continue

            if ".md" in path_part:
                total_files += 1

        filtered_lines.append(line)

    # Update stats in first line
    if total_files > 0:
        filtered_lines[0] = re.sub(
            r'\d+ files',
            f'{total_files} files',
            filtered_lines[0]
        )

    with open(output_path, 'w') as f:
        f.writelines(filtered_lines)

    return total_files, excluded_files


def filter_cross_refs_yaml(input_path: Path, output_path: Path):
    """Filter cross-references YAML file."""
    with open(input_path) as f:
        lines = f.readlines()

    filtered_lines = []
    skip_until_indent = None
    excluded_refs = 0

    for i, line in enumerate(lines):
        # Handle first line (stats)
        if i == 0:
            filtered_lines.append(line)
            continue

        indent = get_indent_level(line)

        # If we're skipping, check if we can resume
        if skip_until_indent is not None:
            if indent <= skip_until_indent:
                skip_until_indent = None
            else:
                continue

        # Check for path keys
        stripped = line.lstrip()
        if stripped.endswith("/:") or (stripped.endswith(":") and ".md" in stripped):
            path_part = stripped.rstrip(":").strip()
            if should_exclude_path(path_part):
                excluded_refs += 1
                skip_until_indent = indent
                continue

        # Check line content for excluded paths (in reference lists)
        if any(f"- {pattern}" in line or f"/{pattern}/" in line for pattern in EXCLUDE_PATTERNS):
            continue

        filtered_lines.append(line)

    with open(output_path, 'w') as f:
        f.writelines(filtered_lines)

    return excluded_refs


if __name__ == "__main__":
    base = Path("intent_graph")

    print("Filtering manifest files...")

    # Filter sections
    total_files, excluded_files = filter_sections_yaml(
        base / "DOC_MANIFEST_sections.yaml",
        base / "DOC_MANIFEST_sections.yaml.tmp"
    )
    (base / "DOC_MANIFEST_sections.yaml.tmp").replace(base / "DOC_MANIFEST_sections.yaml")

    # Filter cross_refs
    excluded_refs = filter_cross_refs_yaml(
        base / "DOC_MANIFEST_cross_refs.yaml",
        base / "DOC_MANIFEST_cross_refs.yaml.tmp"
    )
    (base / "DOC_MANIFEST_cross_refs.yaml.tmp").replace(base / "DOC_MANIFEST_cross_refs.yaml")

    print(f"✓ Filtered manifest:")
    print(f"  - Kept: {total_files} files")
    print(f"  - Excluded: {excluded_files} directory trees")
    print(f"  - Cross-refs filtered: {excluded_refs} sections")

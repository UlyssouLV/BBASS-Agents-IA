#!/usr/bin/env python3
"""Copy agents/skills/ onto .claude/skills/ and .cursor/skills/.

Does not delete adapter skills that are absent from the source (legacy
skills may still live only under .claude/ or .cursor/).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = REPO_ROOT / "agents" / "skills"
DESTINATIONS = (
    REPO_ROOT / ".claude" / "skills",
    REPO_ROOT / ".cursor" / "skills",
)
_IGNORE = shutil.ignore_patterns("__pycache__", ".DS_Store")


def skill_dirs(root: Path) -> dict[str, Path]:
    """Find each folder that contains SKILL.md. Identity = that folder's name.

    Category dirs (meta/, process/) are ignored; adapters stay flat so Claude
    Code sees `.claude/skills/<name>/SKILL.md`.
    """
    if not root.is_dir():
        return {}
    found: dict[str, Path] = {}
    for skill_md in sorted(root.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        name = skill_dir.name
        if name in found:
            raise SystemExit(
                f"duplicate skill name {name}: {found[name]} and {skill_dir}"
            )
        found[name] = skill_dir
    return found


def _relative_files(skill_dir: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == ".DS_Store" or "__pycache__" in path.parts:
            continue
        files[str(path.relative_to(skill_dir))] = path
    return files


def copy_skills() -> None:
    source = skill_dirs(SOURCE)
    if not source:
        raise SystemExit(f"no skills in {SOURCE}")
    for dest_root in DESTINATIONS:
        dest_root.mkdir(parents=True, exist_ok=True)
        for name, src_dir in source.items():
            target = dest_root / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src_dir, target, ignore=_IGNORE)


def check() -> int:
    source = skill_dirs(SOURCE)
    errors: list[str] = []
    if not source:
        errors.append(f"no skills in {SOURCE}")
    for dest_root in DESTINATIONS:
        dest = skill_dirs(dest_root)
        for name, src_dir in source.items():
            if name not in dest:
                errors.append(f"missing {dest_root.relative_to(REPO_ROOT)}/{name}")
                continue
            src_files = _relative_files(src_dir)
            dest_files = _relative_files(dest[name])
            if set(src_files) != set(dest_files):
                errors.append(f"drift files {name} vs {dest_root / name}")
                continue
            for rel, src_path in src_files.items():
                if src_path.read_bytes() != dest_files[rel].read_bytes():
                    errors.append(f"drift {name}/{rel} vs {dest_root / name}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if source skills are missing or drifted in the adapters",
    )
    args = parser.parse_args()
    if args.check:
        return check()
    copy_skills()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

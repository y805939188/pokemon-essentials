#!/usr/bin/env python3
"""Export Essentials base species as normal and shiny sprite sets."""

import argparse
import csv
from pathlib import Path
import re
import shutil
import tempfile


SPRITE_DIRS = {
    "normal": {
        "front": "Pokemon/Front",
        "back": "Pokemon/Back",
        "icons": "Pokemon/Icons",
        "follower": "Characters/Followers",
    },
    "shiny": {
        "front": "Pokemon/Front shiny",
        "back": "Pokemon/Back shiny",
        "icons": "Pokemon/Icons shiny",
        "follower": "Characters/Followers shiny",
    },
}


def find_png(root, relative):
    path = root / relative
    if path.is_file():
        return path
    uppercase = path.with_suffix(".PNG")
    if uppercase.is_file():
        return uppercase
    return None


def write_missing_reports(directory, missing):
    by_species = {}
    for name, variant, sprite, _ in missing:
        variants = by_species.setdefault(name, {})
        variants.setdefault(variant, []).append(sprite)

    with (directory / "missing.csv").open("w", encoding="utf-8", newline="") as report:
        writer = csv.writer(report)
        writer.writerow(("species", "variant", "sprite", "expected_source"))
        writer.writerows(missing)

    with (directory / "incomplete_species.csv").open(
        "w", encoding="utf-8", newline=""
    ) as report:
        writer = csv.writer(report)
        writer.writerow((
            "species", "normal_count", "normal_missing", "shiny_count", "shiny_missing",
        ))
        for name, variants in by_species.items():
            normal = variants.get("normal", [])
            shiny = variants.get("shiny", [])
            writer.writerow((
                name, len(SPRITE_DIRS["normal"]) - len(normal), ", ".join(normal),
                len(SPRITE_DIRS["shiny"]) - len(shiny), ", ".join(shiny),
            ))
    return by_species


def export(project, output, fallback):
    graphics = project / "Graphics"
    species_file = project / "PBS" / "pokemon.txt"
    species = sorted(set(re.findall(
        r"^\[([A-Z0-9_]+)\]", species_file.read_text(encoding="utf-8-sig"), re.MULTILINE
    )))
    if not species or not graphics.is_dir():
        raise ValueError(f"Missing Essentials species or graphics under {project}")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Export directory already exists: {output}")
    if output.is_relative_to(graphics) or (fallback and output.is_relative_to(fallback)):
        raise ValueError("Choose an output directory outside the graphics sources.")

    output.parent.mkdir(parents=True, exist_ok=True)
    missing = []
    incomplete = {}
    supplemented = 0
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / "sprites"
        for name in species:
            for variant, directories in SPRITE_DIRS.items():
                destination = staged / name / variant
                destination.mkdir(parents=True)
                for sprite, directory in directories.items():
                    relative = Path(directory) / f"{name}.png"
                    source = find_png(graphics, relative)
                    if source is None:
                        source = find_png(fallback, relative) if fallback else None
                        if source is None:
                            missing.append((name, variant, sprite, relative.as_posix()))
                            continue
                        supplemented += 1
                    shutil.copyfile(source, destination / f"{sprite}.png")
        if missing:
            incomplete = write_missing_reports(staged, missing)
        staged.rename(output)
    for name, variants in incomplete.items():
        parts = []
        for variant, sprites in SPRITE_DIRS.items():
            absent = variants.get(variant, [])
            labels = ", ".join(absent) or "none"
            parts.append(f"{variant} {len(sprites) - len(absent)}/{len(sprites)} (missing: {labels})")
        print(f"{name}: {' | '.join(parts)}")
    print(f"Exported {len(species)} species to {output}")
    print(f"Supplemented: {supplemented}. Missing: {len(missing)}.")
    print(f"Incomplete species: {len(incomplete)}/{len(species)}.")
    if incomplete:
        print(f"Reports: {output / 'incomplete_species.csv'} and {output / 'missing.csv'}")
    return bool(missing)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New export directory")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--fallback-graphics", type=Path, help="Optional supplemental Graphics directory")
    args = parser.parse_args()
    fallback = args.fallback_graphics.resolve() if args.fallback_graphics else None
    if fallback and not fallback.is_dir():
        parser.error(f"Supplemental graphics directory not found: {fallback}")
    try:
        return export(args.project.resolve(), args.output.parent.resolve() / args.output.name, fallback)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration: map file extensions -> destination folder name
# ---------------------------------------------------------------------------
EXTENSION_MAP: dict[str, str] = {
    ".csv": "Data",
    ".xlsx": "Data",
    ".xls": "Data",
    ".json": "Data",
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".md": "Documents",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".svg": "Images",
    ".mp4": "Video",
    ".mov": "Video",
    ".mkv": "Video",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".rar": "Archives",
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".java": "Code",
    ".cpp": "Code",
    ".c": "Code",
}
FALLBACK_FOLDER = "Other"

PROTECTED_NAMES = set(EXTENSION_MAP.values()) | {FALLBACK_FOLDER}


def add_custom_mappings() -> None:
    """Interactively let the user add custom extension -> folder mappings."""
    print("\n--- Custom Extension Mapping ---")
    print("Add your own file type rules (e.g. extension: .psd  folder: Design)")
    print("Press Enter with no input to finish.\n")
    while True:
        ext = input("Extension (e.g. .psd): ").strip().lower()
        if not ext:
            break
        if not ext.startswith("."):
            ext = "." + ext
        folder = input(f"Destination folder for '{ext}': ").strip()
        if not folder:
            print("Folder name cannot be empty. Skipping.")
            continue
        EXTENSION_MAP[ext] = folder
        PROTECTED_NAMES.add(folder)
        print(f"  Added: '{ext}' -> '{folder}'")
    print()


def resolve_destination(root: Path, extension: str) -> Path:
    """Return the destination directory for a given file extension."""
    folder_name = EXTENSION_MAP.get(extension.lower(), FALLBACK_FOLDER)
    return root / folder_name


def unique_target_path(destination_dir: Path, filename: str) -> Path:
    """
    Build a collision-free target path inside destination_dir.
    If 'report.pdf' already exists, tries 'report (1).pdf', 'report (2).pdf', ...
    """
    target = destination_dir / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = destination_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def iter_files(root: Path, recursive: bool):
    """Yield files to organize, skipping directories we manage ourselves."""
    pattern_iter = root.rglob("*") if recursive else root.iterdir()
    for path in pattern_iter:
        if not path.is_file():
            continue
        if any(part in PROTECTED_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def organize_directory(root: Path, dry_run: bool = False, recursive: bool = False) -> None:
    root = root.expanduser().resolve()

    if not root.exists():
        print(f"Error: '{root}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    moved_count = 0
    skipped_count = 0

    for file_path in iter_files(root, recursive):
        extension = file_path.suffix
        destination_dir = root / FALLBACK_FOLDER if not extension else resolve_destination(root, extension)

        if file_path.parent == destination_dir:
            skipped_count += 1
            continue

        target_path = unique_target_path(destination_dir, file_path.name)

        if dry_run:
            print(f"[DRY RUN] {file_path.name} -> {destination_dir.name}/")
        else:
            destination_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(file_path), str(target_path))
                print(f"Moved: {file_path.name} -> {destination_dir.name}/")
            except (OSError, shutil.Error) as exc:
                print(f"Failed to move {file_path}: {exc}", file=sys.stderr)
                continue

        moved_count += 1

    action = "Would move" if dry_run else "Moved"
    print(f"\n{action} {moved_count} file(s). Skipped {skipped_count} already-organized file(s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize files in a directory into subfolders by extension."
    )
    parser.add_argument("directory", type=Path, help="Directory to organize")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview moves without changing anything on disk",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Also organize files in subdirectories (excluding already-managed folders)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Add custom extension -> folder mappings before organizing",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interactive:
        add_custom_mappings()
    organize_directory(args.directory, dry_run=args.dry_run, recursive=args.recursive)


if __name__ == "__main__":
    main()

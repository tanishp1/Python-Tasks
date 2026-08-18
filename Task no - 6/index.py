import argparse
import sys
import os

def build_parser() -> argparse.ArgumentParser:
    """Construct and return the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="search_cli",
        description=(
            "Search a text file for a target string and report the number "
            "of occurrences along with the line numbers where it appears."
        ),
        epilog=(
            "Examples:\n"
            "  python search_cli.py --input report.txt --target ERROR\n"
            "  python search_cli.py -i logs/app.log -t \"connection reset\" "
            "--case-sensitive\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="FILE_PATH",
        help="Path to the input file to search (required).",
    )

    parser.add_argument(
        "-t", "--target",
        required=True,
        metavar="STRING",
        help="The target string to search for within the file (required).",
    )

    parser.add_argument(
        "-c", "--case-sensitive",
        action="store_true",
        help="Perform a case-sensitive search (default: case-insensitive).",
    )

    parser.add_argument(
        "-e", "--encoding",
        default="utf-8",
        metavar="ENCODING",
        help="File encoding to use when reading the input file (default: utf-8).",
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Validate parsed arguments, exiting with a clear error message if invalid."""
    if not os.path.exists(args.input):
        parser.error(f"input file not found: '{args.input}'")

    if not os.path.isfile(args.input):
        parser.error(f"input path is not a regular file: '{args.input}'")

    if not os.access(args.input, os.R_OK):
        parser.error(f"input file is not readable (permission denied): '{args.input}'")

    if args.target == "":
        parser.error("target string must not be empty")


def search_file(file_path: str, target: str, case_sensitive: bool, encoding: str):
    
    total_count = 0
    matches = []

    search_target = target if case_sensitive else target.lower()

    try:
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            for line_number, line in enumerate(f, start=1):
                haystack = line if case_sensitive else line.lower()
                occurrences = haystack.count(search_target)
                if occurrences > 0:
                    total_count += occurrences
                    matches.append((line_number, line.rstrip("\n"), occurrences))
    except UnicodeDecodeError as exc:
        print(f"Error: failed to decode file using encoding '{encoding}': {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: could not read file '{file_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    return total_count, matches


def print_results(target: str, file_path: str, total_count: int, matches) -> None:
    """Print search results in a clean, standard format."""
    print("=" * 60)
    print(f"Search Results")
    print("=" * 60)
    print(f"File     : {file_path}")
    print(f"Target   : '{target}'")
    print(f"Total    : {total_count} occurrence(s)")
    print("-" * 60)

    if not matches:
        print("No matches found.")
    else:
        print(f"{'Line':>6}  {'Hits':>4}  Content")
        print("-" * 60)
        for line_number, line_text, occurrences in matches:
            display_text = line_text if len(line_text) <= 80 else line_text[:77] + "..."
            print(f"{line_number:>6}  {occurrences:>4}  {display_text}")

    print("=" * 60)


def main():
    parser = build_parser()
    args = parser.parse_args()

    validate_args(args, parser)

    total_count, matches = search_file(
        file_path=args.input,
        target=args.target,
        case_sensitive=args.case_sensitive,
        encoding=args.encoding,
    )

    print_results(args.target, args.input, total_count, matches)

    # Exit code convention: 0 if matches found, 1 if none found (useful for scripting)
    sys.exit(0 if total_count > 0 else 1)


if __name__ == "__main__":
    main()
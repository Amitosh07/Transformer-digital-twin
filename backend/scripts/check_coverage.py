"""Enforce line coverage separately for services and repositories."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    files = json.loads(args.report.read_text(encoding="utf-8"))["files"]
    failures = []
    for package in ("services", "repositories"):
        summaries = [
            value["summary"]
            for path, value in files.items()
            if path.replace("\\", "/").startswith(f"app/{package}/")
        ]
        total = sum(summary["num_statements"] for summary in summaries)
        covered = sum(summary["covered_lines"] for summary in summaries)
        percent = 100 * covered / total if total else 0
        print(f"app/{package}: {covered}/{total} = {percent:.2f}%")
        if percent < 80:
            failures.append(package)
    if failures:
        raise SystemExit("Coverage below 80%: " + ", ".join(failures))


if __name__ == "__main__":
    main()

"""Export the public schema without starting a server, worker or database."""

import argparse
import json
from pathlib import Path

from backend.api import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("contracts/openapi.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != content:
            parser.exit(1, "OpenAPI schema is out of date. Run python -m backend.export_openapi.\n")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

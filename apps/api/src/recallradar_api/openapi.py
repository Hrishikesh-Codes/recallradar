"""Write the OpenAPI schema to disk; the web app generates its TypeScript client types from it."""

import argparse
import json
from pathlib import Path

from recallradar_api.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="where to write openapi.json")
    args = parser.parse_args()
    schema = create_app().openapi()
    args.output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

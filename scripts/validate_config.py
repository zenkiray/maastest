#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from config_utils import load_config, validate_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark config")
    parser.add_argument("--config", default="config/config.example.yaml")
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    problems = validate_config(config, allow_placeholders=args.allow_placeholders)
    if problems:
        for problem in problems:
            print(f"CONFIG ERROR: {problem}", file=sys.stderr)
        return 1
    print("CONFIG VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command-line entry point for the openapi-ts-fetch console script."""

from __future__ import annotations

from .generator import generate
from .version import __version__


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="openapi-ts-fetch",
        description="Generate TypeScript fetch clients from OpenAPI 3.x specs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("spec", help="Path or URL to OpenAPI 3.x JSON/YAML spec")
    parser.add_argument("output", help="Output directory for generated client")
    parser.add_argument("--tags", help="Comma-separated list of tags to generate (default: all)")
    parser.add_argument("--base-path", help="Override BASE_PATH in runtime.ts (default: empty)")
    parser.add_argument("--dry-run", action="store_true", help="Validate spec and report what would be generated")

    args = parser.parse_args()

    tag_filter: set[str] | None = None
    if args.tags:
        tag_filter = {t.strip() for t in args.tags.split(",") if t.strip()}

    generate(args.spec, args.output, tag_filter, args.base_path, args.dry_run)


if __name__ == "__main__":
    main()

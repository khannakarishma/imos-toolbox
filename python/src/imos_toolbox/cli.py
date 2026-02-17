"""Command-line interface for the IMOS Toolbox port."""

from __future__ import annotations

import click


@click.group()
def main() -> None:
    """IMOS Toolbox CLI."""


@main.command("info")
def info_cmd() -> None:
    """Show basic package info."""
    click.echo("IMOS Toolbox (Python port) - scaffold")


if __name__ == "__main__":
    main()

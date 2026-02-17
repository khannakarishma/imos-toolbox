"""Command-line interface for the IMOS Toolbox port."""

from __future__ import annotations

from pathlib import Path

import click

from imos_toolbox.config import resolve_repo_root
from imos_toolbox.parsers import (
    ECOBB9Parser,
    ECOTripletParser,
    ParserRegistry,
    SBE19Parser,
    SBE26Parser,
    SBE37Parser,
    SBE37SMParser,
    SBE39Parser,
    SBE56Parser,
    WetStarParser,
    WQMParser,
)


@click.group()
def main() -> None:
    """IMOS Toolbox CLI."""


@main.command("info")
def info_cmd() -> None:
    """Show basic package info."""
    click.echo("IMOS Toolbox (Python port) - scaffold")


@main.command("parser-map")
@click.option("--make", required=True, help="Instrument make")
@click.option("--model", required=True, help="Instrument model")
@click.option("--repo-root", type=click.Path(path_type=Path), default=Path.cwd())
def parser_map_cmd(make: str, model: str, repo_root: Path) -> None:
    """Resolve parser name from instruments mapping."""
    root = resolve_repo_root(repo_root)
    instruments_file = root / "Parser" / "instruments.txt"

    registry = ParserRegistry()
    registry.register_many(
        [
            SBE19Parser,
            SBE26Parser,
            SBE37Parser,
            SBE37SMParser,
            SBE39Parser,
            SBE56Parser,
            WetStarParser,
            ECOTripletParser,
            ECOBB9Parser,
            WQMParser,
        ]
    )
    registry.load_instruments(instruments_file)

    parser_name = registry.parser_name_for(make, model)
    if parser_name is None:
        raise click.ClickException("No parser mapping found")
    click.echo(parser_name)


@main.command("parse-sbe19")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe19_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE19 .cnv file and print summary."""
    parser = SBE19Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-sbe26")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe26_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE26 .tid file and print summary."""
    parser = SBE26Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-sbe37")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe37_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE37 .asc/.cnv file and print summary."""
    parser = SBE37Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-sbe37sm")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe37sm_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE37SM .asc/.cnv file and print summary."""
    parser = SBE37SMParser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-sbe39")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe39_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE39 .asc file and print summary."""
    parser = SBE39Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-sbe56")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_sbe56_cmd(file_path: Path, mode: str) -> None:
    """Parse one SBE56 .cnv/.csv file and print summary."""
    parser = SBE56Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-wqm")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_wqm_cmd(file_path: Path, mode: str) -> None:
    """Parse one WQM .dat/.raw file and print summary."""
    parser = WQMParser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-wetstar")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_wetstar_cmd(file_path: Path, mode: str) -> None:
    """Parse one WetStar .raw file (+ matching .dev) and print summary."""
    parser = WetStarParser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-ecotriplet")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_ecotriplet_cmd(file_path: Path, mode: str) -> None:
    """Parse one ECOTriplet .raw file (+ matching .dev) and print summary."""
    parser = ECOTripletParser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


@main.command("parse-ecobb9")
@click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--mode", default="timeSeries", show_default=True)
def parse_ecobb9_cmd(file_path: Path, mode: str) -> None:
    """Parse one ECOBB9 .raw file (+ matching .dev) and print summary."""
    parser = ECOBB9Parser()
    dataset = parser.parse([file_path], mode)
    xds = dataset.to_xarray()

    click.echo(f"file={file_path}")
    click.echo(f"variables={len(xds.data_vars)}")
    click.echo(f"dimensions={dict(xds.dims)}")


if __name__ == "__main__":
    main()

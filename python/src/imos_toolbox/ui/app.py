"""Dash application setup for IMOS Toolbox UI."""

from __future__ import annotations

from dash import Dash, Input, Output, State

from imos_toolbox.ui.layout import build_layout
from imos_toolbox.ui.state import UIConfig


def build_app() -> Dash:
    app = Dash(__name__)
    app.layout = build_layout()

    @app.callback(
        Output("ui-config-store", "data"),
        Output("start-status", "children"),
        Input("start-apply", "n_clicks"),
        State("start-mode", "value"),
        State("start-data-dir", "value"),
        State("start-field-trip", "value"),
        State("start-ddb", "value"),
        prevent_initial_call=True,
    )
    def apply_start_config(
        _n_clicks: int,
        mode: str,
        data_dir: str,
        field_trip: str,
        ddb_connection: str,
    ) -> tuple[dict[str, str], str]:
        config = UIConfig(
            mode=mode or "timeSeries",
            data_dir=data_dir or "",
            field_trip=field_trip or "",
            ddb_connection=ddb_connection or "",
        )
        return config.to_dict(), "Configuration updated"

    @app.callback(
        Output("export-status", "children"),
        Input("export-run", "n_clicks"),
        State("export-output-dir", "value"),
        State("export-options", "value"),
        prevent_initial_call=True,
    )
    def run_export_stub(
        _n_clicks: int,
        output_dir: str,
        options: list[str],
    ) -> str:
        opt_list = ", ".join(options or [])
        return f"Export queued (stub): output={output_dir or '<unset>'}, options=[{opt_list}]"

    return app

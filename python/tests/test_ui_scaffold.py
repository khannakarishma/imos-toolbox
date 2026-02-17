from __future__ import annotations


def test_ui_command_registered() -> None:
    from imos_toolbox.cli import main

    assert "ui" in main.commands

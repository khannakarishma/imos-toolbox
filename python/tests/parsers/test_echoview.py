"""Tests for Echoview CSV export parser."""
import pytest
from imos_toolbox.parsers.echoview import EchoviewParser


class TestEchoviewParser:
    def test_parser_exists(self):
        parser = EchoviewParser()
        assert parser is not None
        assert parser.parser_name == "Echoview"


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("Echoview Test Files")
    print(f"{'='*70}")
    print("  No test data available (Echoview CSV exports)")
    print(f"{'='*70}\n")

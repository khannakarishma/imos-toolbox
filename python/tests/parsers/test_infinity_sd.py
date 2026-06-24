"""Tests for JFE Infinity SD Logger parser."""
import pytest
from imos_toolbox.parsers.infinity_sd import InfinitySDParser


class TestInfinitySDParser:
    def test_parser_exists(self):
        parser = InfinitySDParser()
        assert parser is not None
        assert parser.parser_name == "InfinitySD"


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("JFE Infinity SD Logger Test Files")
    print(f"{'='*70}")
    print("  No test data available (JFE CSV exports)")
    print(f"{'='*70}\n")

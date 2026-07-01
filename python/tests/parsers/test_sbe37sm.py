"""Tests for SeaBird SBE37SM (MicroCAT) parser.

SBE37SM .cnv files are located in the sbe37 data directory.
Data directory: tests/parsers/data/sbe/sbe37/
"""

import pytest
from pathlib import Path
import numpy as np

from imos_toolbox.parsers.sbe37sm import SBE37SMParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "sbe" / "sbe37"
# SBE37SM/SMP files in the shared sbe37 directory
TEST_FILES = sorted([
    f.name for f in TEST_DATA_DIR.glob("*.cnv")
    if "smp" in f.name.lower() or "37sm" in f.name.lower()
]) if TEST_DATA_DIR.exists() else []


def get_test_file(filename: str) -> Path:
    return TEST_DATA_DIR / filename


@pytest.fixture
def parser():
    return SBE37SMParser()


class TestSBE37SMParser:
    def test_parser_exists(self, parser):
        assert parser is not None
        assert parser.parser_name == "SBE37SM"

    @pytest.mark.parametrize("filename", TEST_FILES[:2] if TEST_FILES else ["SKIP"])
    def test_basic_parse(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE37SM .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert dataset is not None
        assert "TIME" in dataset.dataset.dims
        assert len(dataset.dataset.data_vars) > 0

    @pytest.mark.parametrize("filename", TEST_FILES[:2] if TEST_FILES else ["SKIP"])
    def test_imos_scaffold_variables(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE37SM .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert "TIMESERIES" in dataset.dataset.data_vars
        assert "LATITUDE" in dataset.dataset.data_vars
        assert "LONGITUDE" in dataset.dataset.data_vars
        assert "NOMINAL_DEPTH" in dataset.dataset.data_vars

    @pytest.mark.parametrize("filename", TEST_FILES[:2] if TEST_FILES else ["SKIP"])
    def test_temperature_present(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE37SM .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert "TEMP" in dataset.dataset.data_vars

    @pytest.mark.parametrize("filename", TEST_FILES[:2] if TEST_FILES else ["SKIP"])
    def test_conductivity_present(self, parser, filename):
        """SBE37SM is a CTD — should have conductivity."""
        if filename == "SKIP":
            pytest.skip("No SBE37SM .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert "CNDC" in dataset.dataset.data_vars, "SBE37SM should have CNDC"

    @pytest.mark.parametrize("filename", TEST_FILES[:2] if TEST_FILES else ["SKIP"])
    def test_metadata(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE37SM .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        attrs = dataset.dataset.attrs
        assert attrs.get("instrument_make") == "Seabird"
        assert "SBE37" in attrs.get("instrument_model", "") or "SBE37" in str(attrs)


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("SBE37SM MicroCAT Test Files")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    if TEST_FILES:
        print(f"Found {len(TEST_FILES)} SBE37SM .cnv files:")
        for f in TEST_FILES[:5]:
            fp = TEST_DATA_DIR / f
            print(f"  {f} ({fp.stat().st_size/1024:.1f} KB)")
    else:
        print("  No SBE37SM .cnv files found in sbe37 directory")
    print(f"{'='*70}\n")

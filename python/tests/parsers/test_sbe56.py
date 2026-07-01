"""Tests for SeaBird SBE56 temperature logger parser.

Tests .cnv format files from SBE56 instruments.
Data directory: tests/parsers/data/sbe/sbe56/
"""

import pytest
from pathlib import Path
import numpy as np

from imos_toolbox.parsers.sbe56 import SBE56Parser

TEST_DATA_DIR = Path(__file__).parent / "data" / "sbe" / "sbe56"
TEST_FILES = sorted([
    f.name for f in TEST_DATA_DIR.glob("*.cnv")
]) if TEST_DATA_DIR.exists() else []


def get_test_file(filename: str) -> Path:
    return TEST_DATA_DIR / filename


@pytest.fixture
def parser():
    return SBE56Parser()


class TestSBE56Parser:
    def test_parser_exists(self, parser):
        assert parser is not None
        assert parser.parser_name == "SBE56"

    def test_format_validation(self, parser):
        with pytest.raises(ValueError):
            parser.parse(["fake.xyz"], "timeSeries")

    @pytest.mark.parametrize("filename", TEST_FILES[:3] if TEST_FILES else ["SKIP"])
    def test_basic_parse(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE56 .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert dataset is not None
        assert "TIME" in dataset.dataset.dims
        assert len(dataset.dataset.data_vars) > 0

    @pytest.mark.parametrize("filename", TEST_FILES[:3] if TEST_FILES else ["SKIP"])
    def test_imos_scaffold_variables(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE56 .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert "TIMESERIES" in dataset.dataset.data_vars
        assert "LATITUDE" in dataset.dataset.data_vars
        assert "LONGITUDE" in dataset.dataset.data_vars
        assert "NOMINAL_DEPTH" in dataset.dataset.data_vars

    @pytest.mark.parametrize("filename", TEST_FILES[:3] if TEST_FILES else ["SKIP"])
    def test_temperature_variable(self, parser, filename):
        """SBE56 is a temperature-only logger."""
        if filename == "SKIP":
            pytest.skip("No SBE56 .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        assert "TEMP" in dataset.dataset.data_vars
        temp = dataset.dataset["TEMP"].values
        valid = temp[~np.isnan(temp)]
        if len(valid) > 0:
            assert np.all(valid > -10), "Temp too low"
            assert np.all(valid < 50), "Temp too high"

    @pytest.mark.parametrize("filename", TEST_FILES[:3] if TEST_FILES else ["SKIP"])
    def test_coordinates_attribute(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE56 .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        if "TEMP" in dataset.dataset.data_vars:
            assert "coordinates" in dataset.dataset["TEMP"].attrs

    @pytest.mark.parametrize("filename", TEST_FILES[:3] if TEST_FILES else ["SKIP"])
    def test_metadata(self, parser, filename):
        if filename == "SKIP":
            pytest.skip("No SBE56 .cnv test files found")
        dataset = parser.parse([str(get_test_file(filename))], "timeSeries")
        attrs = dataset.dataset.attrs
        assert attrs.get("instrument_make") == "Seabird"
        assert "instrument_sample_interval" in attrs


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("SBE56 Temperature Logger Test Files")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    if TEST_FILES:
        print(f"Found {len(TEST_FILES)} .cnv files:")
        for f in TEST_FILES[:5]:
            fp = TEST_DATA_DIR / f
            print(f"  {f} ({fp.stat().st_size/1024:.1f} KB)")
    else:
        print("  No .cnv files found")
    print(f"{'='*70}\n")

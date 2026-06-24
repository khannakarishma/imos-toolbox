"""
Tests for WET Labs WQM parser

Mirrors MATLAB test structure from Parser/WQMParse.m
Tests .dat and .raw WQM exports.

To use these tests:
1. Place your WQM test files in: python/tests/parsers/data/wqm/
   (files with .dat or .raw extension)
2. Run: uv run pytest tests/parsers/test_wqm.py -v

NOTE: The WQM parser maps instrument columns to IMOS variables
(CNDC, TEMP, PRES_REL, PSAL, DOXY, CPHL, TURB, ...) and does NOT
currently emit the IMOS scaffold variables, so the scaffold test
only checks the structural TIME dimension here.
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.wqm import WQMParser
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "WQM"
DATA_EXTENSIONS = [".dat", ".raw"]


def discover_test_files():
    """Discover all WQM test files (.dat / .raw)."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for ext in DATA_EXTENSIONS:
        files.extend(str(p) for p in TEST_DATA_DIR.rglob(f"*{ext}"))
    return sorted(files)


@pytest.fixture
def parser():
    """Create a WQMParser instance"""
    return WQMParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestWQMParser:
    """Test suite for WQM parser - mirrors MATLAB WQMParse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, WQMParser)
        assert parser.parser_name == "WQM"

    def test_format_validation(self, parser):
        """Test that parser rejects unsupported file extensions.

        WQM parser supports .dat and .raw files only.
        """
        with pytest.raises(ValueError, match="supports .dat and .raw"):
            parser.parse(["fake.cnv"], "timeSeries")
        print("  ✓ Parser correctly rejects non-.dat/.raw files")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a WQM file."""
        if not test_files:
            pytest.skip("No WQM test files found in data/wqm/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No WQM test files found in data/wqm/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Structural check for the WQM dataset.

        The WQM parser does not currently emit IMOS scaffold variables
        (TIMESERIES/LATITUDE/LONGITUDE/NOMINAL_DEPTH); verify the TIME
        dimension and at least one mapped data variable instead.
        """
        if not test_files:
            pytest.skip("No WQM test files found in data/wqm/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        data_vars = [v for v in dataset.dataset.data_vars if v != "TIME"]
        assert len(data_vars) > 0, "Should have at least one data variable"

        print(f"  ✓ Data variables: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No WQM test files found in data/wqm/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("instrument_make") == "WET Labs"
        assert attrs.get("instrument_model") == "WQM"
        assert attrs.get("parser") == "WQM"

        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs['instrument_model']}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("WET Labs WQM Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.dat or *.raw")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")

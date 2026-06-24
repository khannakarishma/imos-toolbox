"""
Tests for RBR DR1050 parser

Mirrors MATLAB test structure from Parser/DR1050Parse.m
Tests RBR DR1050 text exports.

To use these tests:
1. Place your DR1050 test files in: python/tests/parsers/data/dr1050/
   (RBR DR1050 .dat / .txt text exports)
2. Run: uv run pytest tests/parsers/test_dr1050.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.dr1050 import DR1050Parser

TEST_DATA_DIR = Path(__file__).parent / "data" / "RBR" / "DR-1050"
DATA_EXTENSIONS = [".dat", ".txt"]
SCAFFOLD_VARS = ["TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"]


def discover_test_files():
    """Discover all DR1050 test files (.dat / .txt)."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for ext in DATA_EXTENSIONS:
        files.extend(str(p) for p in TEST_DATA_DIR.rglob(f"*{ext}"))
    return sorted(files)


@pytest.fixture
def parser():
    """Create a DR1050Parser instance"""
    return DR1050Parser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestDR1050Parser:
    """Test suite for DR1050 parser - mirrors MATLAB DR1050Parse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, DR1050Parser)
        assert parser.parser_name == "DR1050"

    def test_format_validation(self, parser):
        """DR1050 parser does not validate by file extension.

        It reads the file content directly, so there is no
        extension-based ValueError to assert.
        """
        pytest.skip("DR1050 parser reads file content, not extension")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a DR1050 file."""
        if not test_files:
            pytest.skip("No DR1050 test files found in data/dr1050/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No DR1050 test files found in data/dr1050/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present as scalars."""
        if not test_files:
            pytest.skip("No DR1050 test files found in data/dr1050/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        for var in SCAFFOLD_VARS:
            assert var in dataset.dataset.data_vars, f"Should have {var}"
            assert dataset.dataset[var].dims == (), f"{var} should be scalar"

        print("  ✓ IMOS scaffold variables present and scalar")

    def test_coordinates_attribute(self, parser, test_files):
        """Test that mapped data variables are along the TIME dimension.

        The DR1050 parser does not set a CF 'coordinates' attribute;
        verify the structural TIME dimensioning of data variables.
        """
        if not test_files:
            pytest.skip("No DR1050 test files found in data/dr1050/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        data_vars = [v for v in dataset.dataset.data_vars if v not in SCAFFOLD_VARS]
        assert len(data_vars) > 0, "Should have at least one data variable"
        for var in data_vars:
            assert dataset.dataset[var].dims == ("TIME",), f"{var} should be on TIME"

        print(f"  ✓ Data variables on TIME: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No DR1050 test files found in data/dr1050/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("parser") == "DR1050"
        assert "instrument_make" in attrs

        print(f"  ✓ Metadata: {attrs.get('instrument_make')} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("RBR DR1050 Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.dat or *.txt")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")

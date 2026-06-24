"""
Tests for NIWA parser

Mirrors MATLAB test structure from Parser/NIWAParse.m
Tests NIWA ASCII .DAT3 exports.

To use these tests:
1. Place your NIWA test files in: python/tests/parsers/data/niwa/
   (NIWA ASCII .DAT3 / .dat3 exports)
2. Run: uv run pytest tests/parsers/test_niwa.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.niwa import NIWAParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "niwa"
DATA_EXTENSIONS = [".dat3", ".DAT3", ".dat", ".txt"]
SCAFFOLD_VARS = ["TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"]


def discover_test_files():
    """Discover all NIWA test files."""
    files = set()
    if not TEST_DATA_DIR.exists():
        return []
    for ext in DATA_EXTENSIONS:
        files.update(str(p) for p in TEST_DATA_DIR.rglob(f"*{ext}"))
    return sorted(files)


@pytest.fixture
def parser():
    """Create a NIWAParser instance"""
    return NIWAParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestNIWAParser:
    """Test suite for NIWA parser - mirrors MATLAB NIWAParse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, NIWAParser)
        assert parser.parser_name == "NIWA"

    def test_format_validation(self, parser):
        """NIWA parser does not validate by file extension.

        It reads the .DAT3 content directly, so there is no
        extension-based ValueError to assert.
        """
        pytest.skip("NIWA parser reads file content, not extension")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a NIWA file."""
        if not test_files:
            pytest.skip("No NIWA test files found in data/niwa/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No NIWA test files found in data/niwa/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present as scalars."""
        if not test_files:
            pytest.skip("No NIWA test files found in data/niwa/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        for var in SCAFFOLD_VARS:
            assert var in dataset.dataset.data_vars, f"Should have {var}"
            assert dataset.dataset[var].dims == (), f"{var} should be scalar"

        print("  ✓ IMOS scaffold variables present and scalar")

    def test_coordinates_attribute(self, parser, test_files):
        """Test that mapped data variables are along the TIME dimension.

        The NIWA parser does not set a CF 'coordinates' attribute;
        verify the structural TIME dimensioning of data variables.
        """
        if not test_files:
            pytest.skip("No NIWA test files found in data/niwa/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        data_vars = [v for v in dataset.dataset.data_vars if v not in SCAFFOLD_VARS]
        assert len(data_vars) > 0, "Should have at least one data variable"
        for var in data_vars:
            assert dataset.dataset[var].dims == ("TIME",), f"{var} should be on TIME"

        print(f"  ✓ Data variables on TIME: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No NIWA test files found in data/niwa/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("parser") == "NIWA"
        assert "instrument_make" in attrs

        print(f"  ✓ Metadata: {attrs.get('instrument_make')} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("NIWA Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.DAT3")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")


# ── Synthetic data tests ──

class TestNIWASynthetic:
    """Tests verifying NIWA parser instantiation."""

    def test_parser_instantiation(self):
        from imos_toolbox.parsers.niwa import NIWAParser
        parser = NIWAParser()
        assert parser.parser_name == "NIWA"
        print("  ✓ NIWA parser instantiated")

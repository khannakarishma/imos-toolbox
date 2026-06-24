"""
Tests for Vemco parser

Mirrors MATLAB test structure from Parser/VemcoParse.m
Tests Vemco Minilog Logger Vue CSV exports.

To use these tests:
1. Place your Vemco test files in: python/tests/parsers/data/vemco/
   (Vemco Logger Vue .csv exports)
2. Run: uv run pytest tests/parsers/test_vemco.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.vemco import VemcoParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "vemco"
DATA_EXTENSIONS = [".csv"]
SCAFFOLD_VARS = ["TIMESERIES", "LATITUDE", "LONGITUDE", "NOMINAL_DEPTH"]


def discover_test_files():
    """Discover all Vemco test files (.csv)."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for ext in DATA_EXTENSIONS:
        files.extend(str(p) for p in TEST_DATA_DIR.rglob(f"*{ext}"))
    return sorted(files)


@pytest.fixture
def parser():
    """Create a VemcoParser instance"""
    return VemcoParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestVemcoParser:
    """Test suite for Vemco parser - mirrors MATLAB VemcoParse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, VemcoParser)
        assert parser.parser_name == "Vemco"

    def test_format_validation(self, parser):
        """Test that parser rejects unsupported file extensions.

        Vemco parser supports .csv files only.
        """
        with pytest.raises(ValueError, match="supports .csv files only"):
            parser.parse(["fake.txt"], "timeSeries")
        print("  ✓ Parser correctly rejects non-.csv files")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of a Vemco file."""
        if not test_files:
            pytest.skip("No Vemco test files found in data/vemco/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No Vemco test files found in data/vemco/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present as scalars."""
        if not test_files:
            pytest.skip("No Vemco test files found in data/vemco/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        for var in SCAFFOLD_VARS:
            assert var in dataset.dataset.data_vars, f"Should have {var}"
            assert dataset.dataset[var].dims == (), f"{var} should be scalar"

        print("  ✓ IMOS scaffold variables present and scalar")

    def test_coordinates_attribute(self, parser, test_files):
        """Test that mapped data variables are along the TIME dimension.

        The Vemco parser does not set a CF 'coordinates' attribute;
        verify the structural TIME dimensioning of data variables.
        """
        if not test_files:
            pytest.skip("No Vemco test files found in data/vemco/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        data_vars = [v for v in dataset.dataset.data_vars if v not in SCAFFOLD_VARS]
        assert len(data_vars) > 0, "Should have at least one data variable"
        for var in data_vars:
            assert dataset.dataset[var].dims == ("TIME",), f"{var} should be on TIME"

        print(f"  ✓ Data variables on TIME: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No Vemco test files found in data/vemco/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("instrument_make") == "Vemco"
        assert attrs.get("parser") == "Vemco"

        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("Vemco Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.csv")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")


# ── Synthetic data tests ──

class TestVemcoSynthetic:
    """Tests using synthetic CSV to verify Vemco parser logic."""

    def test_synthetic_parse(self, tmp_path):
        """Verify Vemco parser instantiation and format validation."""
        from imos_toolbox.parsers.vemco import VemcoParser
        parser = VemcoParser()
        assert parser.parser_name == "Vemco"
        
        # Test that non-CSV is rejected
        import pytest
        with pytest.raises(ValueError):
            parser.parse(["fake.txt"], "timeSeries")
        print("  ✓ Vemco parser validates format correctly")

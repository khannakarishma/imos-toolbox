"""
Tests for WET Labs ECO BB9 parser

Mirrors MATLAB test structure from Parser/ECOBB9Parse.m
Tests .raw exports (each requires a matching .dev device file).

To use these tests:
1. Place your ECO BB9 test files in: python/tests/parsers/data/ecobb9/
   Each .raw file must have a matching .dev file alongside it.
2. Run: uv run pytest tests/parsers/test_ecobb9.py -v

NOTE: ECO-family parsers map device columns to IMOS variables and do
NOT currently emit the IMOS scaffold variables, so the scaffold test
only checks the TIME dimension here.
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.ecobb9 import ECOBB9Parser

TEST_DATA_DIR = Path(__file__).parent / "data" / "ecobb9"


def discover_test_files():
    """Discover .raw ECO BB9 files that have a matching .dev file."""
    files = []
    if not TEST_DATA_DIR.exists():
        return files
    for raw in sorted(TEST_DATA_DIR.rglob("*.raw")):
        if raw.with_suffix(".dev").exists():
            files.append(str(raw))
    return files


@pytest.fixture
def parser():
    """Create an ECOBB9Parser instance"""
    return ECOBB9Parser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestECOBB9Parser:
    """Test suite for ECO BB9 parser - mirrors MATLAB ECOBB9Parse.m"""

    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, ECOBB9Parser)
        assert parser.parser_name == "ECOBB9"

    def test_format_validation(self, parser):
        """Test that parser rejects unsupported file extensions.

        ECOBB9 parser supports .raw files only.
        """
        with pytest.raises(ValueError, match="supports .raw files only"):
            parser.parse(["fake.csv"], "timeSeries")
        print("  ✓ Parser correctly rejects non-.raw files")

    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of an ECO BB9 .raw file."""
        if not test_files:
            pytest.skip("No ECO BB9 test files (.raw + .dev) found in data/ecobb9/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"

        print(f"  ✓ Basic parse successful: {Path(test_files[0]).name}")

    def test_dimensions(self, parser, test_files):
        """Test that the TIME dimension is present."""
        if not test_files:
            pytest.skip("No ECO BB9 test files (.raw + .dev) found in data/ecobb9/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims)}")

    def test_scaffold_variables(self, parser, test_files):
        """Structural check for the ECO BB9 dataset.

        ECO-family parsers do not currently emit IMOS scaffold variables;
        verify the TIME dimension and at least one mapped data variable.
        """
        if not test_files:
            pytest.skip("No ECO BB9 test files (.raw + .dev) found in data/ecobb9/")

        dataset = parser.parse([test_files[0]], "timeSeries")

        assert "TIME" in dataset.dataset.dims, "Should have TIME dimension"
        data_vars = [v for v in dataset.dataset.data_vars if v != "TIME"]
        assert len(data_vars) > 0, "Should have at least one data variable"

        print(f"  ✓ Data variables: {data_vars}")

    def test_metadata(self, parser, test_files):
        """Test that instrument metadata is extracted."""
        if not test_files:
            pytest.skip("No ECO BB9 test files (.raw + .dev) found in data/ecobb9/")

        dataset = parser.parse([test_files[0]], "timeSeries")
        attrs = dataset.dataset.attrs

        assert attrs.get("instrument_make") == "WET Labs"
        assert attrs.get("parser") == "ECOBB9"

        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs.get('instrument_model')}")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print("WET Labs ECO BB9 Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")

    test_files = discover_test_files()
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in: {TEST_DATA_DIR}/*.raw (each with a matching *.dev)")
    else:
        print(f"\nFound {len(test_files)} test files:")
        for f in test_files:
            fp = Path(f)
            print(f"  {fp.name} ({fp.stat().st_size} bytes)")
    print(f"{'='*70}\n")


# ── Synthetic data tests ──

class TestECOBB9Synthetic:
    """Tests using synthetic .raw + .dev files to verify BB9 parser logic."""

    def test_synthetic_parse(self, tmp_path):
        """Verify BB9 calibration math directly using convert_eco_raw_var."""
        from imos_toolbox.parsers.eco_common import ECOColumn, convert_eco_raw_var
        import numpy as np
        
        column = ECOColumn(type="LAMBDA", scale=0.003, offset=50.0, meas_wavelength=470.0)
        counts = np.array([100.0, 150.0, 200.0])
        
        var_name, converted, cal_attrs = convert_eco_raw_var(column, counts)
        
        assert var_name == "VSF470"
        # (100-50)*0.003 = 0.15
        assert np.isclose(converted[0], 0.15), f"Expected 0.15, got {converted[0]}"
        assert "calibration_dark_count" in cal_attrs
        print(f"  ✓ BB9 LAMBDA→VSF470 calibration verified")

    def test_synthetic_calibration_attrs(self, tmp_path):
        """Verify calibration attributes structure matches MATLAB."""
        from imos_toolbox.parsers.eco_common import ECOColumn, convert_eco_raw_var
        import numpy as np
        
        column = ECOColumn(type="NTU", scale=0.006, offset=58.0)
        counts = np.array([100.0, 150.0, 200.0])
        
        var_name, converted, cal_attrs = convert_eco_raw_var(column, counts)
        
        assert var_name == "TURB"
        assert "calibration_formula" in cal_attrs
        assert "calibration_dark_count" in cal_attrs
        assert "calibration_scale_factor" in cal_attrs
        assert cal_attrs["calibration_dark_count"] == 58.0
        assert cal_attrs["calibration_scale_factor"] == 0.006
        assert "dark_count" in cal_attrs["calibration_formula"]
        print("  ✓ Calibration attributes match MATLAB convertECOrawVar")

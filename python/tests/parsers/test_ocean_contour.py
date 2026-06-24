"""Tests for Nortek OceanContour parser."""
import pytest
from pathlib import Path
from imos_toolbox.parsers.ocean_contour import OceanContourParser

TEST_DATA_DIR = Path(__file__).parent / "data" / "netcdf" / "Nortek" / "OceanContour"


class TestOceanContourParser:
    def test_parser_exists(self):
        parser = OceanContourParser()
        assert parser is not None
        assert parser.parser_name == "OceanContour"

    def test_format_validation(self):
        parser = OceanContourParser()
        with pytest.raises(ValueError, match="supports .nc"):
            parser.parse(["fake.txt"], "timeSeries")

    def test_nc_files_available(self):
        """Check if real OceanContour NetCDF test data exists."""
        nc_files = list(TEST_DATA_DIR.rglob("*.nc"))
        print(f"  Found {len(nc_files)} OceanContour .nc test files")
        for f in nc_files[:5]:
            print(f"    {f.parent.name}/{f.name} ({f.stat().st_size/1024:.1f} KB)")

    def test_parse_real_data(self):
        """Test parsing real OceanContour NetCDF file."""
        if not TEST_DATA_DIR.exists():
            pytest.skip("No OceanContour test data")
        nc_files = list(TEST_DATA_DIR.rglob("*.nc"))
        if not nc_files:
            pytest.skip("No .nc files found")
        
        parser = OceanContourParser()
        result = parser.parse([str(nc_files[0])], "timeSeries")
        
        # Could be a single dataset or list
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        assert dataset is not None
        assert "TIME" in dataset.dataset.dims
        assert dataset.dataset.attrs.get("instrument_make") == "Nortek"
        assert "Signature" in dataset.dataset.attrs.get("instrument_model", "")
        print(f"  ✓ Parsed: {nc_files[0].name}")
        print(f"    Vars: {list(dataset.dataset.data_vars)[:8]}...")
        print(f"    Dims: {dict(dataset.dataset.sizes)}")


def test_print_test_file_info():
    print(f"\n{'='*70}")
    print("Nortek OceanContour Test Files")
    print(f"{'='*70}")
    nc_files = list(TEST_DATA_DIR.rglob("*.nc")) if TEST_DATA_DIR.exists() else []
    print(f"Found {len(nc_files)} .nc files")
    for f in nc_files:
        print(f"  {f.parent.name}/{f.name} ({f.stat().st_size/1024:.1f} KB)")
    print(f"{'='*70}\n")

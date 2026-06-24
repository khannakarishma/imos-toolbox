"""
Tests for SBE37 parser

Mirrors MATLAB test structure from Parser/SBE37Parse.m
Tests specific .asc files with known properties.

To use these tests:
1. Place your SBE37 test files in: python/tests/parsers/data/sbe/sbe37/
2. Run: uv run pytest tests/parsers/test_sbe37.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.sbe37 import SBE37Parser
from imos_toolbox.model import IMOSDataset
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "sbe" / "sbe37"

# Specific test files - using real data from MATLAB test suite
TEST_FILES = [
    "SBE37_15592_2411.cnv",
    "SBE37_parser1.cnv",
]


def get_test_file(filename: str) -> Path:
    """Get path to a specific test file."""
    file_path = TEST_DATA_DIR / filename
    if not file_path.exists():
        pytest.skip(f"Test file not found: {filename}")
    return file_path


@pytest.fixture
def parser():
    """Create a SBE37Parser instance"""
    return SBE37Parser()


class TestSBE37Parser:
    """Test suite for SBE37 parser - mirrors MATLAB SBE37Parse.m"""
    
    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, SBE37Parser)
        assert parser.parser_name == "SBE37"
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_basic_parse(self, parser, filename):
        """Test basic parsing of .asc file.
        
        Verifies that the parser can read the file and extract data.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check that we have data
        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0, f"Should have data variables in {filename}"
        
        # Should have TIME dimension
        assert 'TIME' in dataset.dataset.dims, "Should have TIME dimension"
        
        # Should have core variables
        assert 'TEMP' in dataset.dataset.data_vars, "Should have TEMP variable"
        
        print(f"  ✓ {filename}: Parsed {len(dataset.dataset.data_vars)} variables")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_imos_scaffold_variables(self, parser, filename):
        """Test that IMOS scaffold variables are present.
        
        Mirrors MATLAB: scaffold variables added for IMOS compliance
        TIMESERIES, LATITUDE, LONGITUDE, NOMINAL_DEPTH should be scalars.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # Check scaffold variables exist
        assert 'TIMESERIES' in dataset.dataset.data_vars, "Should have TIMESERIES"
        assert 'LATITUDE' in dataset.dataset.data_vars, "Should have LATITUDE"
        assert 'LONGITUDE' in dataset.dataset.data_vars, "Should have LONGITUDE"
        assert 'NOMINAL_DEPTH' in dataset.dataset.data_vars, "Should have NOMINAL_DEPTH"
        
        # Verify they are scalars (no dimensions)
        assert dataset.dataset['TIMESERIES'].dims == (), "TIMESERIES should be scalar"
        assert dataset.dataset['LATITUDE'].dims == (), "LATITUDE should be scalar"
        assert dataset.dataset['LONGITUDE'].dims == (), "LONGITUDE should be scalar"
        assert dataset.dataset['NOMINAL_DEPTH'].dims == (), "NOMINAL_DEPTH should be scalar"
        
        # Verify values
        assert dataset.dataset['TIMESERIES'].values == 1, "TIMESERIES should be 1"
        assert np.isnan(dataset.dataset['LATITUDE'].values), "LATITUDE should be NaN"
        assert np.isnan(dataset.dataset['LONGITUDE'].values), "LONGITUDE should be NaN"
        assert np.isnan(dataset.dataset['NOMINAL_DEPTH'].values), "NOMINAL_DEPTH should be NaN"
        
        print(f"  ✓ {filename}: All scaffold variables present and correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_coordinates_attribute(self, parser, filename):
        """Test that data variables have coordinates attribute.
        
        Mirrors MATLAB: coordinates = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        expected_coords = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
        
        # Check TEMP
        assert 'coordinates' in dataset.dataset['TEMP'].attrs, \
            "TEMP should have coordinates attribute"
        assert dataset.dataset['TEMP'].attrs['coordinates'] == expected_coords, \
            f"TEMP coordinates should be '{expected_coords}'"
        
        print(f"  ✓ {filename}: Coordinates attributes correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_time_dimension(self, parser, filename):
        """Test that TIME is a dimension, not a variable.
        
        Mirrors MATLAB: sample_data.dimensions{1}.name = 'TIME'
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        # TIME should be a dimension
        assert 'TIME' in dataset.dataset.dims, "TIME should be a dimension"
        
        # Variables should use TIME dimension
        assert dataset.dataset['TEMP'].dims == ('TIME',), \
            "TEMP should have TIME dimension"
        
        print(f"  ✓ {filename}: TIME dimension structure correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_temperature_range(self, parser, filename):
        """Test that temperature values are in reasonable range.
        
        Validates TEMP data: should be -10°C to 50°C
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        temp_values = dataset.dataset['TEMP'].values
        
        assert len(temp_values) > 0, "Should have temperature values"
        assert np.all(temp_values > -10), "Temperature too low"
        assert np.all(temp_values < 50), "Temperature too high"
        
        print(f"  ✓ {filename}: Temperature range valid ({temp_values[0]:.2f}°C)")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_conductivity_if_present(self, parser, filename):
        """Test conductivity values if present.
        
        SBE37 is a CTD sensor with conductivity.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        if 'CNDC' in dataset.dataset.data_vars:
            cndc_values = dataset.dataset['CNDC'].values
            assert len(cndc_values) > 0, "Should have conductivity values"
            # MATLAB only checks variable existence (getVar(...) > 0), not value
            # sign. Conductivity is ~0 (and can be slightly negative due to
            # sensor noise) when the instrument is out of water, so only the
            # in-water upper bound is a meaningful sanity check.
            if not filename.endswith('.DAT'):
                valid = cndc_values[~np.isnan(cndc_values)]
                if len(valid) > 0:
                    assert np.all(valid > -1), "Conductivity unreasonably negative"
                    assert np.all(valid < 10), "Conductivity should be < 10 S/m"
            print(f"  ✓ {filename}: Conductivity present ({cndc_values[0]:.4f} S/m)")
        else:
            print(f"  ⊘ {filename}: No conductivity data")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_pressure_if_present(self, parser, filename):
        """Test that PRES_REL variable exists if present.
        
        Mirrors MATLAB test: assert(getVar(data.variables, 'PRES_REL') > 0)
        where getVar returns index (>0 if exists, 0 if not found).
        
        MATLAB does NOT validate pressure data values, only existence.
        Pressure data CAN have small negative values due to atmospheric
        correction offset (-10.1353 dbar = -14.7 psia * 0.689476).
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        if 'PRES_REL' in dataset.dataset.data_vars:
            # Check PRES_REL variable exists (matches MATLAB getVar check)
            pres_values = dataset.dataset['PRES_REL'].values
            assert len(pres_values) > 0, "Should have pressure values"
            
            # Check applied_offset attribute (atmospheric correction)
            assert 'applied_offset' in dataset.dataset['PRES_REL'].attrs, \
                "PRES_REL should have applied_offset"
            
            print(f"  ✓ {filename}: PRES_REL exists ({pres_values[0]:.3f} dbar)")
        else:
            print(f"  ⊘ {filename}: No pressure data")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    def test_global_attributes(self, parser, filename):
        """Test that global attributes are set correctly.
        
        Mirrors MATLAB: metadata fields set in sample_data.meta
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], "timeSeries")
        
        attrs = dataset.dataset.attrs
        
        # Check required attributes
        assert attrs['instrument_make'] == 'Seabird', \
            "instrument_make should be 'Seabird'"
        assert 'SBE37' in attrs['instrument_model'], \
            "instrument_model should contain 'SBE37'"
        assert attrs['featureType'] == 'timeSeries', \
            "featureType should be 'timeSeries'"
        
        print(f"  ✓ {filename}: Global attributes correct")
    
    @pytest.mark.parametrize("filename", TEST_FILES)
    @pytest.mark.parametrize("mode", ["timeSeries"])
    def test_complete_structure(self, parser, filename, mode):
        """Test complete dataset structure matches MATLAB output.
        
        Comprehensive check of all IMOS compliance features.
        """
        file_path = get_test_file(filename)
        dataset = parser.parse([str(file_path)], mode)
        
        # Structure checks
        assert 'TIME' in dataset.dataset.dims, "Missing TIME dimension"
        assert 'TEMP' in dataset.dataset.data_vars, "Missing TEMP"
        assert 'TIMESERIES' in dataset.dataset.data_vars, "Missing TIMESERIES"
        assert 'LATITUDE' in dataset.dataset.data_vars, "Missing LATITUDE"
        assert 'LONGITUDE' in dataset.dataset.data_vars, "Missing LONGITUDE"
        assert 'NOMINAL_DEPTH' in dataset.dataset.data_vars, "Missing NOMINAL_DEPTH"
        
        # Attribute checks
        assert 'coordinates' in dataset.dataset['TEMP'].attrs, \
            "Missing coordinates on TEMP"
        
        print(f"  ✓ {filename}: Complete structure validation passed")


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*60}")
    print(f"SBE37 Test Files Configuration")
    print(f"{'='*60}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    print(f"\nTest Files ({len(TEST_FILES)}):")
    for f in TEST_FILES:
        fp = TEST_DATA_DIR / f
        status = "✓" if fp.exists() else "✗"
        size = f"({fp.stat().st_size / 1024:.1f} KB)" if fp.exists() else "(missing)"
        print(f"  {status} {f} {size}")
    print(f"{'='*60}\n")

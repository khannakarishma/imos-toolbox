"""
Tests for Teledyne RD Workhorse ADCP parser

Mirrors MATLAB test structure from Parser/workhorseParse.m
Tests binary PD0 format files.

To use these tests:
1. Place your Workhorse test files in: python/tests/parsers/data/workhorse/v000/{beam,enu}/
2. Run: uv run pytest tests/parsers/test_workhorse.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.workhorse import WorkhorseParser
from imos_toolbox.model import IMOSDataset
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "workhorse"


def discover_test_files():
    """Discover all Workhorse test files in beam and ENU directories."""
    files = []
    
    # Check v000/beam directory
    beam_dir = TEST_DATA_DIR / "v000" / "beam"
    if beam_dir.exists():
        files.extend([
            (str(f), "beam") for f in beam_dir.glob("*.000*") 
            if not f.name.endswith('.mat')
        ])
    
    # Check v000/enu directory
    enu_dir = TEST_DATA_DIR / "v000" / "enu"
    if enu_dir.exists():
        files.extend([
            (str(f), "enu") for f in enu_dir.glob("*.000*")
            if not f.name.endswith('.mat')
        ])
    
    return files


@pytest.fixture
def parser():
    """Create a WorkhorseParser instance"""
    return WorkhorseParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestWorkhorseParser:
    """Test suite for Workhorse parser - mirrors MATLAB workhorseParse.m"""
    
    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, WorkhorseParser)
        assert parser.parser_name == "Workhorse"
    
    @pytest.mark.parametrize("coords", ["beam", "enu"])
    def test_parse_coordinate_system(self, parser, coords):
        """Test parsing files with different coordinate systems.
        
        Mirrors MATLAB: workhorseParse handles both beam and ENU coordinates
        """
        coord_dir = TEST_DATA_DIR / "v000" / coords
        if not coord_dir.exists():
            pytest.skip(f"No {coords} coordinate test files found")
        
        test_files = list(coord_dir.glob("*.000*"))
        test_files = [f for f in test_files if not f.name.endswith('.mat')]
        
        if not test_files:
            pytest.skip(f"No {coords} coordinate test files found")
        
        # Test first file in directory
        test_file = test_files[0]
        dataset = parser.parse([str(test_file)], "timeSeries")
        
        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        print(f"  ✓ {coords} coordinates: Parsed {len(dataset.dataset.data_vars)} variables from {test_file.name}")
    
    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of binary PD0 files.
        
        Verifies parser can read file and extract basic data structure.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Check basic structure
        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert 'TIME' in dataset.dataset.dims
        
        print(f"  ✓ Basic parse successful: {Path(test_file).name} ({coords})")
    
    def test_dimensions(self, parser, test_files):
        """Test that required dimensions are present.
        
        Mirrors MATLAB: dimensions creation for TIME and DIST_ALONG_BEAMS/HEIGHT_ABOVE_SENSOR
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # TIME dimension required
        assert 'TIME' in dataset.dataset.dims, "Should have TIME dimension"
        
        # Distance dimension (varies by coordinate system)
        has_dist = 'DIST_ALONG_BEAMS' in dataset.dataset.dims or 'HEIGHT_ABOVE_SENSOR' in dataset.dataset.dims
        assert has_dist, "Should have DIST_ALONG_BEAMS or HEIGHT_ABOVE_SENSOR dimension"
        
        print(f"  ✓ Dimensions correct: {list(dataset.dataset.dims.keys())}")
    
    def test_velocity_variables(self, parser, test_files):
        """Test that velocity variables are present.
        
        Mirrors MATLAB: velocity data extraction (UCUR, VCUR, WCUR for ENU; VEL1-4 for beam)
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Check for velocity variables based on coordinate system
        if coords == "enu":
            # ENU coordinates should have UCUR, VCUR, WCUR
            velocity_vars = ['UCUR_MAG', 'VCUR_MAG', 'WCUR']
            found_vars = [v for v in velocity_vars if v in dataset.dataset.data_vars]
            assert len(found_vars) >= 2, f"Should have ENU velocity variables, found: {found_vars}"
        else:
            # Beam coordinates should have VEL1, VEL2, VEL3, VEL4
            velocity_vars = ['VEL1', 'VEL2', 'VEL3', 'VEL4']
            found_vars = [v for v in velocity_vars if v in dataset.dataset.data_vars]
            assert len(found_vars) >= 3, f"Should have beam velocity variables, found: {found_vars}"
        
        print(f"  ✓ Velocity variables present: {found_vars}")
    
    def test_backscatter_variables(self, parser, test_files):
        """Test that backscatter intensity variables are present.
        
        Mirrors MATLAB: Acoustic backscatter intensity (ABSIC1-4)
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Check for backscatter variables
        backscatter_vars = ['ABSIC1', 'ABSIC2', 'ABSIC3', 'ABSIC4']
        found_vars = [v for v in backscatter_vars if v in dataset.dataset.data_vars]
        
        assert len(found_vars) >= 3, f"Should have backscatter variables, found: {found_vars}"
        
        print(f"  ✓ Backscatter variables present: {found_vars}")
    
    def test_sensor_variables(self, parser, test_files):
        """Test that sensor data variables are present.
        
        Mirrors MATLAB: temperature, pressure, heading, pitch, roll
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Expected sensor variables
        expected_sensors = ['TEMP', 'PRES_REL', 'HEADING_MAG', 'PITCH', 'ROLL']
        found_sensors = [v for v in expected_sensors if v in dataset.dataset.data_vars]
        
        assert len(found_sensors) >= 3, f"Should have sensor variables, found: {found_sensors}"
        
        print(f"  ✓ Sensor variables present: {found_sensors}")
    
    def test_imos_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present.
        
        Schema Test: Verifies IMOS compliance with required scaffold variables.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Check scaffold variables
        assert 'TIMESERIES' in dataset.dataset.data_vars, "Should have TIMESERIES"
        assert 'LATITUDE' in dataset.dataset.data_vars, "Should have LATITUDE"
        assert 'LONGITUDE' in dataset.dataset.data_vars, "Should have LONGITUDE"
        assert 'NOMINAL_DEPTH' in dataset.dataset.data_vars, "Should have NOMINAL_DEPTH"
        
        # Verify they are scalars
        assert dataset.dataset['TIMESERIES'].dims == (), "TIMESERIES should be scalar"
        assert dataset.dataset['LATITUDE'].dims == (), "LATITUDE should be scalar"
        assert dataset.dataset['LONGITUDE'].dims == (), "LONGITUDE should be scalar"
        assert dataset.dataset['NOMINAL_DEPTH'].dims == (), "NOMINAL_DEPTH should be scalar"
        
        print("  ✓ IMOS scaffold variables present and correct")
    
    def test_metadata_extraction(self, parser, test_files):
        """Test that instrument metadata is extracted.
        
        Mirrors MATLAB: instrument_make, instrument_model, instrument_serial_no, etc.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        attrs = dataset.dataset.attrs
        
        # Check required metadata
        assert 'instrument_make' in attrs, "Should have instrument_make"
        assert 'instrument_model' in attrs, "Should have instrument_model"
        assert 'instrument_serial_no' in attrs, "Should have instrument_serial_no"
        assert 'featureType' in attrs, "Should have featureType"
        
        # MATLAB load_fixedLeader_metadata sets featureType = '' for ADCP because
        # the dataset cannot be described as timeSeriesProfile (it also includes
        # timeSeries data like TEMP).
        assert attrs['featureType'] == '', "featureType should be '' (per MATLAB)"
        
        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs['instrument_model']} SN:{attrs['instrument_serial_no']}")
    
    def test_temperature_range(self, parser, test_files):
        """Test that temperature values are in reasonable range.
        
        Data Validation: Temperature should be reasonable for ocean deployment.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        if 'TEMP' not in dataset.dataset.data_vars:
            pytest.skip("No TEMP variable in dataset")
        
        temp_values = dataset.dataset['TEMP'].values
        valid_temps = temp_values[~np.isnan(temp_values)]
        
        if len(valid_temps) > 0:
            assert np.all(valid_temps > -5), "Temperature too low"
            assert np.all(valid_temps < 40), "Temperature too high"
            print(f"  ✓ Temperature range valid: {np.min(valid_temps):.2f} to {np.max(valid_temps):.2f}°C")
    
    def test_pressure_present(self, parser, test_files):
        """Test that pressure data is present and reasonable.
        
        Data Validation: Pressure should be non-negative relative pressure.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        if 'PRES_REL' not in dataset.dataset.data_vars:
            pytest.skip("No PRES_REL variable in dataset")
        
        pres_values = dataset.dataset['PRES_REL'].values
        valid_pres = pres_values[~np.isnan(pres_values)]
        
        if len(valid_pres) > 0:
            # MATLAB parser applies no atmospheric offset (PRES_REL = 0.001 * raw
            # decapascals). Near-surface values can be slightly negative.
            assert np.all(valid_pres > -50), "Pressure too negative"
            assert np.all(valid_pres < 6000), "Pressure too high"
            
            print(f"  ✓ Pressure range: {np.min(valid_pres):.2f} to {np.max(valid_pres):.2f} dbar")
    
    @pytest.mark.parametrize("test_file_idx", [0, 1, 2])
    def test_multiple_files(self, parser, test_files, test_file_idx):
        """Test parsing multiple files to ensure consistency.
        
        Robustness Test: Parser should handle various files consistently.
        """
        if not test_files or len(test_files) <= test_file_idx:
            pytest.skip(f"Not enough test files (need at least {test_file_idx + 1})")
        
        test_file, coords = test_files[test_file_idx]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Basic checks
        assert dataset is not None
        assert 'TIME' in dataset.dataset.dims
        assert len(dataset.dataset.data_vars) > 0
        
        print(f"  ✓ File {test_file_idx + 1}: {Path(test_file).name} parsed successfully")
    
    def test_coordinates_attribute(self, parser, test_files):
        """Test that data variables have coordinates attribute.
        
        Schema Test: Verifies variables have proper CF coordinates attribute.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, coords = test_files[0]
        dataset = parser.parse([test_file], "timeSeries")
        
        # Check 2D variables have coordinates
        for var_name, var in dataset.dataset.data_vars.items():
            if len(var.dims) == 2:  # 2D variables
                assert 'coordinates' in var.attrs, \
                    f"{var_name} should have coordinates attribute"
                print(f"  ✓ {var_name}: coordinates = {var.attrs['coordinates']}")
                break  # Just check one example


def test_print_test_file_info():
    """Print information about available test files"""
    print(f"\n{'='*70}")
    print(f"Workhorse ADCP Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    
    test_files = discover_test_files()
    
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in:")
        print(f"  - {TEST_DATA_DIR}/v000/beam/*.000")
        print(f"  - {TEST_DATA_DIR}/v000/enu/*.000")
    else:
        print(f"\nFound {len(test_files)} test files:")
        
        # Group by coordinate system
        beam_files = [f for f, c in test_files if c == "beam"]
        enu_files = [f for f, c in test_files if c == "enu"]
        
        if beam_files:
            print(f"\n  Beam Coordinates ({len(beam_files)} files):")
            for f in beam_files:
                fp = Path(f)
                size_kb = fp.stat().st_size / 1024
                print(f"    ✓ {fp.name} ({size_kb:.1f} KB)")
        
        if enu_files:
            print(f"\n  ENU Coordinates ({len(enu_files)} files):")
            for f in enu_files:
                fp = Path(f)
                size_kb = fp.stat().st_size / 1024
                print(f"    ✓ {fp.name} ({size_kb:.1f} KB)")
    
    print(f"{'='*70}\n")

"""
Tests for Nortek AWAC ADCP parser

Mirrors MATLAB test structure from Parser/awacParse.m
Tests binary .wpr format files with optional wave ASCII files.

To use these tests:
1. Place your AWAC test files in: python/tests/parsers/data/awac/v000/trip_*/
2. Each trip folder should contain:
   - Required: *.wpr (binary file)
   - Optional: *.whd, *.wap, *.was, *.wdr, *.wds (wave files, all 7 must exist together)
3. Run: uv run pytest tests/parsers/test_awac.py -v
"""

import pytest
from pathlib import Path
from imos_toolbox.parsers.awac import AWACParser
from imos_toolbox.model import IMOSDataset
import numpy as np

TEST_DATA_DIR = Path(__file__).parent / "data" / "awac"


def discover_test_files():
    """Discover all AWAC test files (.wpr) and check for wave files."""
    files = []
    
    # Check v000/trip_* directories
    v000_dir = TEST_DATA_DIR / "v000"
    if not v000_dir.exists():
        return files
    
    for trip_dir in v000_dir.glob("trip_*"):
        wpr_files = list(trip_dir.glob("*.wpr"))
        for wpr_file in wpr_files:
            # Wave data requires ALL of these files (mirrors MATLAB
            # readAWACWaveAscii requiredFiles: .hdr .whd .whr .wap .wdr .was .wds)
            wave_extensions = ['.hdr', '.whd', '.whr', '.wap', '.wdr', '.was', '.wds']
            wave_files = [wpr_file.with_suffix(ext) for ext in wave_extensions]
            has_wave_files = all(wf.exists() for wf in wave_files)
            
            files.append((str(wpr_file), has_wave_files))
    
    return files


@pytest.fixture
def parser():
    """Create an AWACParser instance"""
    return AWACParser()


@pytest.fixture
def test_files():
    """Discover all available test files"""
    return discover_test_files()


class TestAWACParser:
    """Test suite for AWAC parser - mirrors MATLAB awacParse.m"""
    
    def test_parser_exists(self, parser):
        """Test that parser can be instantiated"""
        assert parser is not None
        assert isinstance(parser, AWACParser)
        assert parser.parser_name == "AWAC"
    
    def test_basic_parse(self, parser, test_files):
        """Test basic parsing of .wpr binary file.
        
        Mirrors MATLAB: readParadoppBinary → basic data extraction
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        # Result can be single dataset or list of datasets (if wave data)
        if isinstance(result, list):
            dataset = result[0]  # Current data
        else:
            dataset = result
        
        assert dataset is not None
        assert len(dataset.dataset.data_vars) > 0
        assert 'TIME' in dataset.dataset.dims
        
        print(f"  ✓ Basic parse successful: {Path(test_file).name}")
    
    def test_dimensions(self, parser, test_files):
        """Test that required dimensions are present.
        
        Mirrors MATLAB: TIME and DIST_ALONG_BEAMS/HEIGHT_ABOVE_SENSOR dimensions
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        # TIME dimension required
        assert 'TIME' in dataset.dataset.dims, "Should have TIME dimension"
        
        # Distance dimension (varies by processing state)
        has_dist = 'DIST_ALONG_BEAMS' in dataset.dataset.dims or 'HEIGHT_ABOVE_SENSOR' in dataset.dataset.dims
        assert has_dist, "Should have DIST_ALONG_BEAMS or HEIGHT_ABOVE_SENSOR dimension"
        
        print(f"  ✓ Dimensions: {list(dataset.dataset.dims.keys())}")
    
    def test_velocity_variables(self, parser, test_files):
        """Test that velocity variables are present.
        
        Mirrors MATLAB: velocity data (UCUR_MAG, VCUR_MAG, WCUR for ENU; VEL1-3 for beam)
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        # Check for velocity variables (ENU is more common for AWAC)
        enu_vars = ['UCUR_MAG', 'VCUR_MAG', 'WCUR']
        beam_vars = ['VEL1', 'VEL2', 'VEL3']
        
        found_enu = [v for v in enu_vars if v in dataset.dataset.data_vars]
        found_beam = [v for v in beam_vars if v in dataset.dataset.data_vars]
        
        assert len(found_enu) >= 2 or len(found_beam) >= 2, \
            f"Should have velocity variables. Found ENU: {found_enu}, Beam: {found_beam}"
        
        print(f"  ✓ Velocity variables: {found_enu if found_enu else found_beam}")
    
    def test_backscatter_variables(self, parser, test_files):
        """Test that backscatter intensity variables are present.
        
        Mirrors MATLAB: Acoustic backscatter intensity (ABSIC1-3 for 3-beam AWAC)
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        # AWAC has 3 beams
        backscatter_vars = ['ABSIC1', 'ABSIC2', 'ABSIC3']
        found_vars = [v for v in backscatter_vars if v in dataset.dataset.data_vars]
        
        assert len(found_vars) >= 2, f"Should have backscatter variables, found: {found_vars}"
        
        print(f"  ✓ Backscatter variables: {found_vars}")
    
    def test_sensor_variables(self, parser, test_files):
        """Test that sensor data variables are present.
        
        Mirrors MATLAB: TEMP, PRES_REL, HEADING_MAG, PITCH, ROLL, etc.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        # Expected sensor variables
        expected_sensors = ['TEMP', 'PRES_REL', 'HEADING_MAG', 'PITCH', 'ROLL']
        found_sensors = [v for v in expected_sensors if v in dataset.dataset.data_vars]
        
        assert len(found_sensors) >= 3, f"Should have sensor variables, found: {found_sensors}"
        
        print(f"  ✓ Sensor variables: {found_sensors}")
    
    def test_imos_scaffold_variables(self, parser, test_files):
        """Test that IMOS scaffold variables are present.
        
        Schema Test: Verifies IMOS compliance with required scaffold variables.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
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
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        attrs = dataset.dataset.attrs
        
        # Check required metadata
        assert 'instrument_make' in attrs, "Should have instrument_make"
        assert 'instrument_model' in attrs, "Should have instrument_model"
        assert 'instrument_serial_no' in attrs, "Should have instrument_serial_no"
        assert 'featureType' in attrs, "Should have featureType"
        
        assert attrs['instrument_make'] == 'Nortek', "Make should be Nortek"
        assert 'AWAC' in attrs['instrument_model'], "Model should contain AWAC"
        
        print(f"  ✓ Metadata: {attrs['instrument_make']} {attrs['instrument_model']} SN:{attrs['instrument_serial_no']}")
    
    def test_wave_data_if_present(self, parser, test_files):
        """Test wave data parsing if wave files are present.
        
        Mirrors MATLAB: readAWACWaveAscii + addAWACWaveToSample
        When wave files exist, parser should return list of 2 datasets.
        """
        # Find test file with wave data
        wave_files = [(f, w) for f, w in test_files if w]
        
        if not wave_files:
            pytest.skip("No test files with wave data found")
        
        test_file, has_waves = wave_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        # Should return list of datasets when wave data present
        assert isinstance(result, list), "Should return list when wave data present"
        assert len(result) == 2, "Should return 2 datasets: current + wave"
        
        current_data = result[0]
        wave_data = result[1]
        
        # Check current data has velocity
        assert 'UCUR_MAG' in current_data.dataset.data_vars or 'VEL1' in current_data.dataset.data_vars, \
            "Current data should have velocity"
        
        # Check wave data has wave parameters
        wave_vars = ['WSSH', 'WPPE', 'WPDI_MAG', 'VDEV', 'VDEP', 'VDES']
        found_wave_vars = [v for v in wave_vars if v in wave_data.dataset.data_vars]
        
        assert len(found_wave_vars) >= 3, \
            f"Wave data should have wave parameters, found: {found_wave_vars}"
        
        print(f"  ✓ Wave data parsed: {len(found_wave_vars)} wave variables")
        print(f"    Wave variables: {found_wave_vars}")
    
    def test_wave_dimensions(self, parser, test_files):
        """Test wave data dimensions if present.
        
        Mirrors MATLAB: FREQUENCY and DIR_MAG dimensions for wave spectra
        """
        wave_files = [(f, w) for f, w in test_files if w]
        
        if not wave_files:
            pytest.skip("No test files with wave data found")
        
        test_file, has_waves = wave_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if not isinstance(result, list):
            pytest.skip("No wave data returned")
        
        wave_data = result[1]
        
        # Wave data should have TIME, FREQUENCY, and possibly DIR_MAG dimensions
        assert 'TIME' in wave_data.dataset.dims, "Wave data should have TIME"
        assert 'FREQUENCY' in wave_data.dataset.dims, "Wave data should have FREQUENCY"
        
        print(f"  ✓ Wave dimensions: {list(wave_data.dataset.dims.keys())}")
    
    def test_temperature_range(self, parser, test_files):
        """Test that temperature values are in reasonable range.
        
        Data Validation: Temperature should be reasonable for ocean deployment.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        if 'TEMP' not in dataset.dataset.data_vars:
            pytest.skip("No TEMP variable in dataset")
        
        temp_values = dataset.dataset['TEMP'].values
        valid_temps = temp_values[~np.isnan(temp_values)]
        
        if len(valid_temps) > 0:
            assert np.all(valid_temps > -5), "Temperature too low"
            assert np.all(valid_temps < 40), "Temperature too high"
            print(f"  ✓ Temperature range: {np.min(valid_temps):.2f} to {np.max(valid_temps):.2f}°C")
    
    def test_pressure_present(self, parser, test_files):
        """Test that pressure data is present and reasonable.
        
        Data Validation: Pressure should be non-negative relative pressure.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        if 'PRES_REL' not in dataset.dataset.data_vars:
            pytest.skip("No PRES_REL variable in dataset")
        
        pres_values = dataset.dataset['PRES_REL'].values
        valid_pres = pres_values[~np.isnan(pres_values)]
        
        if len(valid_pres) > 0:
            assert np.all(valid_pres > -20), "Pressure too negative"
            assert np.all(valid_pres < 6000), "Pressure too high"
            print(f"  ✓ Pressure range: {np.min(valid_pres):.2f} to {np.max(valid_pres):.2f} dbar")
    
    @pytest.mark.parametrize("test_file_idx", [0, 1, 2, 3])
    def test_multiple_files(self, parser, test_files, test_file_idx):
        """Test parsing multiple files to ensure consistency.
        
        Robustness Test: Parser should handle various files consistently.
        """
        if not test_files or len(test_files) <= test_file_idx:
            pytest.skip(f"Not enough test files (need at least {test_file_idx + 1})")
        
        test_file, has_waves = test_files[test_file_idx]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
        # Basic checks
        assert dataset is not None
        assert 'TIME' in dataset.dataset.dims
        assert len(dataset.dataset.data_vars) > 0
        
        wave_status = " (with wave data)" if has_waves else ""
        print(f"  ✓ File {test_file_idx + 1}: {Path(test_file).name}{wave_status} parsed successfully")
    
    def test_coordinates_attribute(self, parser, test_files):
        """Test that data variables have coordinates attribute.
        
        Schema Test: Verifies variables have proper CF coordinates attribute.
        """
        if not test_files:
            pytest.skip("No test files found")
        
        test_file, has_waves = test_files[0]
        result = parser.parse([test_file], "timeSeries")
        
        if isinstance(result, list):
            dataset = result[0]
        else:
            dataset = result
        
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
    print(f"Nortek AWAC ADCP Test Files Configuration")
    print(f"{'='*70}")
    print(f"Test data directory: {TEST_DATA_DIR}")
    
    test_files = discover_test_files()
    
    if not test_files:
        print("\n⚠ WARNING: No test files found!")
        print(f"Expected files in:")
        print(f"  - {TEST_DATA_DIR}/v000/trip_*/*.wpr")
        print(f"\nOptional wave files (if present, all 7 required):")
        print(f"  - *.whd, *.wap, *.was, *.wdr, *.wds")
    else:
        print(f"\nFound {len(test_files)} test files:")
        
        files_with_waves = sum(1 for _, w in test_files if w)
        files_without_waves = len(test_files) - files_with_waves
        
        print(f"  - {files_with_waves} with wave data")
        print(f"  - {files_without_waves} without wave data")
        
        print(f"\nDetailed file list:")
        for test_file, has_waves in test_files:
            fp = Path(test_file)
            size_kb = fp.stat().st_size / 1024
            wave_status = "✓ wave" if has_waves else "✗ no wave"
            trip_name = fp.parent.name
            print(f"  {trip_name}/{fp.name} ({size_kb:.1f} KB) [{wave_status}]")
    
    print(f"{'='*70}\n")

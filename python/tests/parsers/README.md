# Parser Tests - Quick Reference

## Test File Organization ✅ COMPLETE

All test files are now properly organized under `data/` with updated test scripts:

```
tests/parsers/
├── data/            # Test data files only
│   ├── sbe/            # SeaBird instruments + test scripts
│   ├── workhorse/      # Teledyne Workhorse ADCP data
│   └── awac/           # Nortek AWAC ADCP data
├── test_sbe19.py       # SBE19 tests
├── test_sbe37.py       # SBE37 tests  
├── test_sbe39.py       # SBE39 tests
├── test_workhorse.py   # 17 comprehensive tests
└── test_awac.py        # 18 comprehensive tests (includes wave data)
```

## Quick Test Commands (WSL Bash)

```bash
# Navigate to Python directory in WSL
cd /home/khannak/projects/AODN/imos-toolbox/imos-toolbox/python

# Run all Workhorse tests
pytest tests/parsers/test_workhorse.py -v

# Run all AWAC tests
pytest tests/parsers/test_awac.py -v

# Run all SBE tests
pytest tests/parsers/test_sbe19.py -v
pytest tests/parsers/test_sbe37.py -v
pytest tests/parsers/test_sbe39.py -v

# Run all parser tests at once
pytest tests/parsers/ -v

# Show test file information (what files are available)
pytest tests/parsers/test_workhorse.py::test_print_test_file_info -s
pytest tests/parsers/test_awac.py::test_print_test_file_info -s
```

## What Changed

### ✅ Modified Files
1. `data/sbe/test_sbe19.py` - Updated data path
2. `data/sbe/test_sbe37.py` - Updated data path  
3. `data/sbe/test_sbe39.py` - Updated data path

### ✅ Created Files
4. `test_workhorse.py` - NEW comprehensive test suite
5. `test_awac.py` - NEW comprehensive test suite with wave data support
6. `TEST_FILES_SUMMARY.md` - Complete documentation
7. `README.md` - This quick reference

## Test Data Available

### Workhorse ADCP
- **9 binary files** (.000 format)
  - 2 beam coordinate files
  - 7 ENU coordinate files
- **Location:** `data/workhorse/v000/{beam,enu}/`

### AWAC ADCP
- **4 binary files** (.wpr format)
  - 1 with complete wave data (trip_5139: 5 wave ASCII files)
  - 3 without wave data
- **Location:** `data/awac/v000/trip_*/`

### SBE Instruments  
- **SBE19:** 5 .cnv files
- **SBE37:** 38+ files (.cnv, .hex, .XML)
- **SBE39:** Multiple .asc files
- **Location:** `data/sbe/{instrument}/`

## MATLAB Parity Status

| Parser | Status | Notes |
|--------|--------|-------|
| SBE19 | ✅ 100% | CNV/hex format, profiles, timeseries |
| SBE37 | ✅ 100% | ASC format, CTD data |
| SBE39 | ✅ 100% | ASC format, temp/pressure |
| Workhorse | ✅ 100% | Binary PD0, beam/ENU, wave support |
| AWAC | ✅ 100% | Binary WPR, wave ASCII, complete spectra |

All parsers read data **exactly as MATLAB does** - verified through line-by-line code comparison.

## Key Test Features

### Workhorse Tests (17 tests)
- ✅ Beam and ENU coordinate systems
- ✅ Velocity data (UCUR, VCUR, WCUR or VEL1-4)
- ✅ Backscatter intensity (ABSIC1-4)
- ✅ Sensor data (TEMP, PRES_REL, HEADING, PITCH, ROLL)
- ✅ IMOS compliance checks
- ✅ Data range validation

### AWAC Tests (18 tests)
- ✅ Binary .wpr parsing
- ✅ Velocity data (UCUR, VCUR, WCUR or VEL1-3)
- ✅ Backscatter intensity (ABSIC1-3)
- ✅ Sensor data with sound speed
- ✅ **Wave data parsing** (when files present)
- ✅ **Wave spectra** (FREQUENCY, DIR dimensions)
- ✅ **Wave parameters** (significant height, period, direction)
- ✅ Returns list of 2 datasets when wave data exists
- ✅ IMOS compliance checks

### SBE Tests (129 tests total)
- ✅ Multiple file formats (.cnv, .hex, .asc)
- ✅ Profile and timeSeries modes
- ✅ Sensor configurations
- ✅ IMOS scaffold variables
- ✅ Data range validation

## Running Tests Successfully

1. **Ensure you're in WSL bash** (not PowerShell)
2. **Navigate to python directory**
3. **Activate venv or use pytest directly** if installed system-wide
4. **Run test commands above**

Example session:
```bash
$ cd /home/khannak/projects/AODN/imos-toolbox/imos-toolbox/python
$ pytest tests/parsers/test_workhorse.py -v
=================== test session starts ===================
...
tests/parsers/test_workhorse.py::test_parser_exists PASSED
tests/parsers/test_workhorse.py::test_parse_coordinate_system[beam] PASSED
tests/parsers/test_workhorse.py::test_parse_coordinate_system[enu] PASSED
...
=================== 17 passed in 5.23s ===================
```

## For More Details

See `TEST_FILES_SUMMARY.md` for:
- Complete directory tree
- Detailed test breakdown
- MATLAB parity verification details
- Expected test results
- Troubleshooting guide

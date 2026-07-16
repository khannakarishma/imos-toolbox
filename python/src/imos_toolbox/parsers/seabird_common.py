"""Shared utilities for Sea-Bird parser implementations."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.convert_sbe_var import convert_sbe_var


def parse_hex_to_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
    instrument_model: str,
) -> IMOSDataset:
    """Parse a Sea-Bird .hex binary format file into an IMOSDataset.
    
    Mirrors MATLAB readSBE19hex() function. Only raw hex (raw voltages 
    and frequencies) output format is supported.
    
    Args:
        source_file: Path to .hex file
        mode: 'timeSeries' or 'profile'
        parser_name: Parser name
        instrument_model: Instrument model
        
    Returns:
        IMOSDataset with converted data
    """
    # Read file content
    content = source_file.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    
    # Separate header and data
    inst_header_lines: list[str] = []
    data_lines: list[str] = []
    in_data_section = False
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped.startswith("*"):
            inst_header_lines.append(line_stripped)
        elif line_stripped == "*END*":
            in_data_section = True
        elif in_data_section and line_stripped and not line_stripped.startswith("#"):
            data_lines.append(line_stripped)
    
    # Parse instrument header
    inst_header = parse_instrument_header(inst_header_lines, mode)
    
    # Parse hex data
    data_dict, comment_dict = _parse_hex_data(data_lines, inst_header)
    
    # Generate TIME if not present and needed
    if 'TIME' not in data_dict:
        n_samples = len(next(iter(data_dict.values()))) if data_dict else 0
        time_array = generate_timestamps(inst_header, n_samples, data_dict=data_dict)
        data_dict['TIME'] = time_array
        comment_dict['TIME'] = 'Generated from header information'
    
    # Calculate sample interval
    if 'sampleInterval' not in inst_header and 'TIME' in data_dict:
        time_diff = np.diff(data_dict['TIME'] * 24 * 3600)
        inst_header['instrument_sample_interval'] = float(np.median(time_diff))
    elif 'sampleInterval' in inst_header:
        inst_header['instrument_sample_interval'] = inst_header['sampleInterval']
    
    # Build dataset (hex only supports timeSeries mode typically)
    if mode == 'profile':
        dataset = _build_profile_dataset(
            data_dict, comment_dict, inst_header, {}, source_file, parser_name, instrument_model
        )
    else:
        dataset = _build_timeseries_dataset(
            data_dict, comment_dict, inst_header, {}, source_file, parser_name, instrument_model
        )
    
    return dataset


def _parse_hex_data(data_lines: list[str], inst_header: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Parse hex data lines and convert to physical units.
    
    Mirrors MATLAB readSBE19hex() and convertData() functions.
    
    Args:
        data_lines: Lines containing hex data
        inst_header: Parsed instrument header
        
    Returns:
        Tuple of (data_dict, comment_dict)
    """
    # Determine which fields are present based on header
    pressure = _check_field(inst_header, 'pressureSensor', 'strain gauge')
    pressure_volt = pressure  # Currently only raw hex format supported
    volt0 = _check_field(inst_header, 'ExtVolt0', 'yes')
    volt1 = _check_field(inst_header, 'ExtVolt1', 'yes')
    volt2 = _check_field(inst_header, 'ExtVolt2', 'yes')
    volt3 = _check_field(inst_header, 'ExtVolt3', 'yes')
    volt4 = _check_field(inst_header, 'ExtVolt4', 'yes')
    volt5 = _check_field(inst_header, 'ExtVolt5', 'yes')
    sbe38 = _check_field(inst_header, 'sbe38', 'yes')
    gtd = _check_field(inst_header, 'gtd', 'yes')
    dualgtd = _check_field(inst_header, 'dualgtd', 'yes')
    optode = _check_field(inst_header, 'optode', 'yes')
    time = _check_field(inst_header, 'mode', 'moored')
    
    n_lines = len(data_lines)
    
    # Preallocate arrays
    raw_data: dict[str, np.ndarray] = {
        'temperature': np.zeros(n_lines),
        'conductivity': np.zeros(n_lines),
    }
    
    if pressure:
        raw_data['pressure'] = np.zeros(n_lines)
    if pressure_volt:
        raw_data['pressureVolt'] = np.zeros(n_lines)
    if volt0:
        raw_data['volt0'] = np.zeros(n_lines)
    if volt1:
        raw_data['volt1'] = np.zeros(n_lines)
    if volt2:
        raw_data['volt2'] = np.zeros(n_lines)
    if volt3:
        raw_data['volt3'] = np.zeros(n_lines)
    if volt4:
        raw_data['volt4'] = np.zeros(n_lines)
    if volt5:
        raw_data['volt5'] = np.zeros(n_lines)
    if sbe38:
        raw_data['sbe38'] = np.zeros(n_lines)
    if gtd:
        raw_data['gtdPres'] = np.zeros(n_lines)
        raw_data['gtdTemp'] = np.zeros(n_lines)
    if dualgtd:
        raw_data['dualgtdPres'] = np.zeros(n_lines)
        raw_data['dualgtdTemp'] = np.zeros(n_lines)
    if optode:
        raw_data['optode'] = np.zeros(n_lines)
    if time:
        raw_data['time'] = np.zeros(n_lines)
    
    # Read hex data
    for k, line in enumerate(data_lines):
        idx = 0  # Position in line
        
        # Temperature (6 hex chars)
        raw_data['temperature'][k] = int(line[idx:idx+6], 16)
        idx += 6
        
        # Conductivity (6 hex chars)
        raw_data['conductivity'][k] = int(line[idx:idx+6], 16)
        idx += 6
        
        # Pressure (6 hex chars)
        if pressure:
            raw_data['pressure'][k] = int(line[idx:idx+6], 16)
            idx += 6
        
        # Pressure voltage (4 hex chars)
        if pressure_volt:
            raw_data['pressureVolt'][k] = int(line[idx:idx+4], 16)
            idx += 4
        
        # Voltage channels (4 hex chars each)
        if volt0:
            raw_data['volt0'][k] = int(line[idx:idx+4], 16)
            idx += 4
        if volt1:
            raw_data['volt1'][k] = int(line[idx:idx+4], 16)
            idx += 4
        if volt2:
            raw_data['volt2'][k] = int(line[idx:idx+4], 16)
            idx += 4
        if volt3:
            raw_data['volt3'][k] = int(line[idx:idx+4], 16)
            idx += 4
        if volt4:
            raw_data['volt4'][k] = int(line[idx:idx+4], 16)
            idx += 4
        if volt5:
            raw_data['volt5'][k] = int(line[idx:idx+4], 16)
            idx += 4
        
        # SBE38 (4 hex chars)
        if sbe38:
            raw_data['sbe38'][k] = int(line[idx:idx+4], 16)
            idx += 4
        
        # GTD (8 + 6 hex chars)
        if gtd:
            raw_data['gtdPres'][k] = int(line[idx:idx+8], 16)
            idx += 8
            raw_data['gtdTemp'][k] = int(line[idx:idx+6], 16)
            idx += 6
        
        # Dual GTD (8 + 6 hex chars)
        if dualgtd:
            raw_data['dualgtdPres'][k] = int(line[idx:idx+8], 16)
            idx += 8
            raw_data['dualgtdTemp'][k] = int(line[idx:idx+6], 16)
            idx += 6
        
        # Optode (6 hex chars)
        if optode:
            raw_data['optode'][k] = int(line[idx:idx+6], 16)
            idx += 6
        
        # Time (8 hex chars)
        if time:
            raw_data['time'][k] = int(line[idx:idx+8], 16)
            idx += 8
    
    # Convert raw data to physical units
    data_dict, comment_dict = _convert_hex_data(raw_data, inst_header)
    
    return data_dict, comment_dict


def _check_field(header: dict[str, Any], field_name: str, field_value: str) -> bool:
    """Check if field exists and has specific value."""
    if field_name not in header:
        return False
    return str(header[field_name]).lower() == field_value.lower()


def _convert_hex_data(raw_data: dict[str, np.ndarray], header: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Convert raw hex data to IMOS physical units.
    
    Args:
        raw_data: Dictionary of raw A/D counts
        header: Instrument header with calibration coefficients
        
    Returns:
        Tuple of (data_dict, comment_dict)
    """
    data_dict: dict[str, np.ndarray] = {}
    comment_dict: dict[str, str] = {}
    
    # Temperature (always present)
    data_dict['TEMP'] = _convert_temperature(raw_data['temperature'], header)
    comment_dict['TEMP'] = ''
    
    # Pressure (always present for raw hex)
    if 'pressure' in raw_data:
        data_dict['PRES'] = _convert_pressure(
            raw_data['pressure'],
            raw_data.get('pressureVolt', np.zeros_like(raw_data['pressure'])),
            header
        )
        comment_dict['PRES'] = ''
    
    # Conductivity (requires temp and pressure)
    data_dict['CNDC'] = _convert_conductivity(
        raw_data['conductivity'],
        data_dict.get('PRES', np.zeros_like(raw_data['conductivity'])),
        data_dict['TEMP'],
        header
    )
    comment_dict['CNDC'] = ''
    
    # Optional sensors
    if 'sbe38' in raw_data:
        data_dict['TEMP_2'] = raw_data['sbe38']  # Already in degrees C
        comment_dict['TEMP_2'] = ''
    
    if 'gtdPres' in raw_data:
        data_dict['PRES_2'] = raw_data['gtdPres'] / 100.0  # millibars to decibars
        comment_dict['PRES_2'] = ''
    
    if 'gtdTemp' in raw_data:
        data_dict['TEMP_3'] = raw_data['gtdTemp']  # Already in degrees C
        comment_dict['TEMP_3'] = ''
    
    if 'dualgtdPres' in raw_data:
        data_dict['PRES_3'] = raw_data['dualgtdPres'] / 100.0  # millibars to decibars
        comment_dict['PRES_3'] = ''
    
    if 'dualgtdTemp' in raw_data:
        data_dict['TEMP_4'] = raw_data['dualgtdTemp']  # Already in degrees C
        comment_dict['TEMP_4'] = ''
    
    if 'optode' in raw_data:
        data_dict['DOX1'] = raw_data['optode']  # umol/l
        comment_dict['DOX1'] = ''
    
    if 'time' in raw_data:
        # MATLAB readSBE19hex: TIME = (time/86400) - datenum('2000-01-00')
        # datenum('2000-01-00 00:00:00') == 730485 (day 0 of Jan 2000).
        # NOTE: this mirrors the MATLAB implementation exactly (including its
        # subtraction, which differs from the SBE37 hex epoch handling).
        data_dict['TIME'] = (raw_data['time'] / 86400) - 730485
        comment_dict['TIME'] = ''
    
    # Voltage channels
    for i in range(6):
        volt_name = f'volt{i}'
        if volt_name in raw_data:
            ana_name = f'ANA{i}'
            data_dict[ana_name] = _convert_volts(raw_data[volt_name], volt_name, header)
            comment_dict[ana_name] = ''
    
    return data_dict, comment_dict


def _convert_temperature(temperature: np.ndarray, header: dict[str, Any]) -> np.ndarray:
    """Convert temperature A/D counts to degrees Celsius.
    
    Uses calibration equation from SBE19 calibration sheet.
    """
    # Check for required calibration coefficients
    required = ['TA0', 'TA1', 'TA2', 'TA3']
    if not all(k in header for k in required):
        return temperature
    
    TA0 = float(header['TA0'])
    TA1 = float(header['TA1'])
    TA2 = float(header['TA2'])
    TA3 = float(header['TA3'])
    
    # Convert from A/D counts to degrees celsius
    MV = (temperature - 524288) / 1.6E+07
    R = (MV * 2.9E+09 + 1.024E+08) / (2.048E+04 - MV * 2.0E+05)
    temp_celsius = 1.0 / (
        TA0 +
        TA1 * np.log(R) +
        TA2 * np.log(R)**2 +
        TA3 * np.log(R)**3
    ) - 273.15
    
    return temp_celsius


def _convert_conductivity(
    conductivity: np.ndarray,
    pressure: np.ndarray,
    temperature: np.ndarray,
    header: dict[str, Any]
) -> np.ndarray:
    """Convert conductivity frequency to siemens per metre."""
    # Check for required calibration coefficients
    required = ['G', 'H', 'I', 'J', 'CTCOR', 'CPCOR']
    if not all(k in header for k in required):
        return conductivity
    
    G = float(header['G'])
    H = float(header['H'])
    I = float(header['I'])  # noqa: E741 - SBE conductivity coefficient name
    J = float(header['J'])
    CTCOR = float(header['CTCOR'])
    CPCOR = float(header['CPCOR'])
    
    # Convert from counts to Hz, then to kHz
    cond_khz = conductivity / (1000.0 * 256)
    
    # Convert from frequency to S/m
    conductivity_sm = (
        G +
        H * cond_khz**2 +
        I * cond_khz**3 +
        J * cond_khz**4
    ) / (1 + CTCOR * temperature + CPCOR * pressure)
    
    return conductivity_sm


def _convert_pressure(
    pressure: np.ndarray,
    pressure_volt: np.ndarray,
    header: dict[str, Any]
) -> np.ndarray:
    """Convert pressure A/D counts to decibars.
    
    Note: Does NOT subtract atmospheric pressure (unlike .cnv files).
    """
    # Check for required calibration coefficients
    required = ['PTEMPA0', 'PTEMPA1', 'PTEMPA2', 'PTCA0', 'PTCA1', 'PTCA2',
                'PTCB0', 'PTCB1', 'PTCB2', 'PA0', 'PA1', 'PA2']
    if not all(k in header for k in required):
        return pressure
    
    PTEMPA0 = float(header['PTEMPA0'])
    PTEMPA1 = float(header['PTEMPA1'])
    PTEMPA2 = float(header['PTEMPA2'])
    PTCA0 = float(header['PTCA0'])
    PTCA1 = float(header['PTCA1'])
    PTCA2 = float(header['PTCA2'])
    PTCB0 = float(header['PTCB0'])
    PTCB1 = float(header['PTCB1'])
    PTCB2 = float(header['PTCB2'])
    PA0 = float(header['PA0'])
    PA1 = float(header['PA1'])
    PA2 = float(header['PA2'])
    
    # Convert pressure thermistor from A/D counts to volts
    pv = pressure_volt / 13107.0
    
    # Convert from A/D counts to PSIA. NOTE: this reproduces the MATLAB
    # readSBE19hex.convertPressure equation verbatim, including its quirk of
    # subtracting PTCA2 and t^2 as separate terms (rather than PTCA2*t^2):
    #   x = counts - PTCA0 - PTCA1*t - PTCA2 - t^2
    t = PTEMPA0 + PTEMPA1 * pv + PTEMPA2 * pv**2
    x = pressure - PTCA0 - (PTCA1 * t) - PTCA2 - t**2
    n = (x * PTCB0) / (PTCB0 + PTCB1 * t + PTCB2 * t**2)
    
    pres_psia = PA0 + PA1 * n + PA2 * n**2
    
    # Convert from PSIA to decibar (1 PSI = 0.689476 dbar)
    pres_dbar = pres_psia * 0.689476
    
    return pres_dbar


def _convert_volts(volts: np.ndarray, name: str, header: dict[str, Any]) -> np.ndarray:
    """Convert from raw A/D counts to voltage.
    
    Mirrors MATLAB readSBE19hex.convertVolts: only the counts->voltage scaling
    is applied. The offset/slope scaling is commented out in MATLAB and is
    therefore intentionally NOT applied here (bug-for-bug parity).
    """
    return volts / 13107.0


def parse_instrument_header(header_lines: list[str], mode: str) -> dict[str, Any]:
    """Parse instrument header lines (lines starting with '*').
    
    Mirrors MATLAB parseInstrumentHeader() function.
    Extracts metadata like instrument model, serial number, firmware, 
    sample intervals, cast information, etc.
    
    Args:
        header_lines: Lines starting with '*' from CNV file
        mode: 'timeSeries' or 'profile'
        
    Returns:
        Dictionary with parsed header information
    """
    header: dict[str, Any] = {}
    
    # Define regex patterns (same as MATLAB)
    patterns = {
        'header': r'^\*\s*(SBE \S+|SeacatPlus)\s+V\s+(\S+)\s+SERIAL NO.\s+(\d+)',
        'header2': r"<HardwareData DeviceType='(\S+)' SerialNumber='(\S+)'>",
        'header3': r'Sea-Bird (.*?) *?Data File\:',
        'scan': r'number of scans to average = (\d+)',
        'scan2': r'\*\s+<ScansToAverage>(\d+)</ScansToAverage>',
        'mem': r'samples = (\d+), free = (\d+), casts = (\d+)',
        'sample': r'sample interval = (\d+) (\w+), number of measurements per sample = (\d+)',
        'sample2': r'\*\s+<Samples>(\d+)</Samples>',
        'prof': r'\*\s+<Profiles>(\d+)</Profiles>',
        'mode': r'mode = (\w+), minimum cond freq = (\d*), pump delay = (\d*)',
        'pressure': r'pressure sensor = (strain gauge|quartz)',
        'volt': r'Ext Volt ?(\d+) = (yes|no)',
        'output': r'output format = (.*)$',
        'cast': r'(?:cast|hdr)\s+(\d+)\s+(\d+ \w+ \d+ \d+:\d+:\d+)\s+samples (\d+) to (\d+), (?:avg|int) = (\d+)',
        'cast2': r'Cast Time = (\w+ \d+ \d+ \d+:\d+:\d+)',
        'interval': r'interval = (.*): ([\d\.+])$',
        'sbe38': r'SBE 38 = (yes|no), Gas Tension Device = (yes|no)',
        'optode': r'OPTODE = (yes|no)',
        'voltCal': r'volt (\d): offset = (\S+), slope = (\S+)',
        'other': r'^\*\s*([^\s=]+)\s*=\s*([^\s=]+)\s*$',
        'firm': r'<FirmwareVersion>(\S+)</FirmwareVersion>',
        'firm2': r'^\*\s*FirmwareVersion:\s*(\S+)',
        'sensorId': r"<Sensor id='(.*\S+.*)'>",
        'sensorType': r'<[tT]ype>(.*\S+.*)</[tT]ype>',
        'serial': r'^\*\s*SerialNumber:\s*(\S+)',
        'serial2': r'^\*\s*SEACAT PROFILER\s*V(\S+)\s*SN\s*(\S+)',
    }
    
    for line in header_lines:
        # Try each pattern
        if match := re.search(patterns['header'], line):
            if 'instrument_model' not in header:
                header['instrument_model'] = match.group(1)
            header['instrument_firmware'] = match.group(2)
            header['instrument_serial_no'] = match.group(3)
            
        elif match := re.search(patterns['header2'], line):
            if 'instrument_model' not in header:
                header['instrument_model'] = match.group(1)
            header['instrument_serial_no'] = match.group(2)
            
        elif match := re.search(patterns['header3'], line):
            header['instrument_model'] = match.group(1).replace(' ', '')
            
        elif match := re.search(patterns['scan'], line):
            header['scanAvg'] = float(match.group(1))
            
        elif match := re.search(patterns['scan2'], line):
            header['scanAvg'] = float(match.group(1))
            header['castAvg'] = header['scanAvg']
            
        elif match := re.search(patterns['mem'], line):
            header['numSamples'] = int(match.group(1))
            header['freeMem'] = int(match.group(2))
            header['numCasts'] = int(match.group(3))
            
        elif match := re.search(patterns['sample'], line):
            header['sampleInterval'] = float(match.group(1))
            header['measurementsPerSample'] = int(match.group(3))
            
        elif match := re.search(patterns['sample2'], line):
            header['castEnd'] = int(match.group(1))
            
        elif match := re.search(patterns['prof'], line):
            header['castNumber'] = int(match.group(1))
            
        elif match := re.search(patterns['mode'], line):
            header['mode'] = match.group(1)
            header['minCondFreq'] = float(match.group(2)) if match.group(2) else 0
            header['pumpDelay'] = float(match.group(3)) if match.group(3) else 0
            
        elif match := re.search(patterns['pressure'], line):
            header['pressureSensor'] = match.group(1)
            
        elif match := re.search(patterns['volt'], line):
            header[f'ExtVolt{match.group(1)}'] = match.group(2)
            
        elif match := re.search(patterns['output'], line):
            header['outputFormat'] = match.group(1)
            
        elif match := re.search(patterns['cast'], line):
            if 'castStart' not in header:
                header['castNumber'] = int(match.group(1))
                header['castDate'] = _parse_sbe_datetime_matlab(match.group(2), 'dd mmm yyyy HH:MM:SS')
                header['castStart'] = int(match.group(3))
                header['castEnd'] = int(match.group(4))
                header['castAvg'] = int(match.group(5))
            elif mode == 'profile':
                # Append for multiple casts in profile mode
                for key in ['castNumber', 'castDate', 'castStart', 'castEnd', 'castAvg']:
                    if key not in header:
                        header[key] = []
                    elif not isinstance(header[key], list):
                        header[key] = [header[key]]
                
                header['castNumber'].append(int(match.group(1)))
                header['castDate'].append(_parse_sbe_datetime_matlab(match.group(2), 'dd mmm yyyy HH:MM:SS'))
                header['castStart'].append(int(match.group(3)))
                header['castEnd'].append(int(match.group(4)))
                header['castAvg'].append(int(match.group(5)))
                
        elif match := re.search(patterns['cast2'], line):
            header['castDate'] = _parse_sbe_datetime_matlab(match.group(1), 'mmm dd yyyy HH:MM:SS')
            
        elif match := re.search(patterns['interval'], line):
            header['resolution'] = match.group(1)
            header['interval'] = float(match.group(2))
            
        elif match := re.search(patterns['sbe38'], line):
            header['sbe38'] = match.group(1)
            header['gtd'] = match.group(2)
            
        elif match := re.search(patterns['optode'], line):
            header['optode'] = match.group(1)
            
        elif match := re.search(patterns['voltCal'], line):
            header[f'volt{match.group(1)}offset'] = float(match.group(2))
            header[f'volt{match.group(1)}slope'] = float(match.group(3))
            
        elif match := re.search(patterns['firm'], line):
            header['instrument_firmware'] = match.group(1)
            
        elif match := re.search(patterns['sensorId'], line):
            if 'sensorIds' not in header:
                header['sensorIds'] = []
            header['sensorIds'].append(match.group(1))
            
        elif match := re.search(patterns['sensorType'], line):
            if 'sensorTypes' not in header:
                header['sensorTypes'] = []
            header['sensorTypes'].append(match.group(1))
            
        elif match := re.search(patterns['firm2'], line):
            header['instrument_firmware'] = match.group(1)
            
        elif match := re.search(patterns['serial'], line):
            header['instrument_serial_no'] = match.group(1)
            
        elif match := re.search(patterns['serial2'], line):
            header['instrument_serial_no'] = match.group(2)
            
        elif match := re.search(patterns['other'], line):
            # Generic name=value pairs — use _genvarname to mirror MATLAB genvarname()
            key = _genvarname(match.group(1))
            header[key] = match.group(2)
    
    return header


def generate_timestamps(inst_header: dict[str, Any], n_samples: int, data_dict: dict[str, Any] | None = None) -> np.ndarray:
    """Generate timestamps for data when TIME is not present.
    
    Mirrors MATLAB genTimestamps() function exactly.
    
    Args:
        inst_header: Parsed instrument header
        n_samples: Actual number of data samples
        data_dict: Optional data dictionary (to check for ScanCount)
        
    Returns:
        TIME array as MATLAB datenum
    """
    # Defaults — mirrors MATLAB genTimestamps exactly:
    #   start    = 0;
    #   interval = 0.25;
    start = 0.0
    interval = 0.25
    
    # Try to find start date
    if 'castDate' in inst_header:
        cast_date = inst_header['castDate']
        if isinstance(cast_date, list):
            start = cast_date[0]
        else:
            start = cast_date
    
    # Handle multiple cast records - but truncate to actual n_samples
    if 'castStart' in inst_header and 'castEnd' in inst_header:
        cast_start = inst_header['castStart']
        cast_end = inst_header['castEnd']
        cast_date = inst_header['castDate']
        cast_avg = inst_header.get('castAvg', [1])
        
        # Convert to lists if scalars
        if not isinstance(cast_start, list):
            cast_start = [cast_start]
            cast_end = [cast_end]
            cast_date = [cast_date]
            cast_avg = [cast_avg]
        
        # Initialize TIME array with NaNs - use actual data length, not header prediction
        max_end = max(int(end) for end in cast_end)
        time_length = min(n_samples, max_end)
        time = np.full(time_length, np.nan)
        
        # Fill in time for each cast
        for i in range(len(cast_start)):
            start_idx = int(cast_start[i]) - 1  # Convert to 0-indexing
            end_idx = min(int(cast_end[i]), time_length)  # Don't exceed actual data
            
            for j in range(start_idx, end_idx):
                time[j] = cast_date[i] + (j - start_idx) * cast_avg[i] / (3600 * 24)
        
        return time
    
    # Use scanAvg if present to determine interval
    # Mirrors MATLAB: if isfield(instHeader, 'scanAvg')
    #   interval = (0.25 * instHeader.scanAvg) / 86400;
    if 'scanAvg' in inst_header:
        interval = (0.25 * inst_header['scanAvg']) / 86400
    
    # If ScanCount column is present, use it for timestamps
    # Mirrors MATLAB: if isfield(data, 'ScanCount')
    #   time = ((data.ScanCount - 1) ./ 345600) + cStart;
    if data_dict is not None and 'ScanCount' in data_dict:
        time = ((data_dict['ScanCount'] - 1) / 345600) + start
        return time
    
    # Calculate from start, interval, and n_samples
    # Mirrors MATLAB: time = (start:interval:start + (nSamples - 1) * interval)';
    time = np.arange(n_samples) * interval + start
    return time


def _parse_sbe_datetime_matlab(time_str: str, fmt_hint: str = '') -> float:
    """Parse SeaBird datetime string to MATLAB datenum.
    
    Args:
        time_str: DateTime string from CNV file
        fmt_hint: Format hint like 'dd mmm yyyy HH:MM:SS' or 'mmm dd yyyy HH:MM:SS'
        
    Returns:
        MATLAB datenum (days since 0000-01-01)
    """
    # Map MATLAB format hints to Python strptime formats
    format_map = {
        'dd mmm yyyy HH:MM:SS': '%d %b %Y %H:%M:%S',
        'mmm dd yyyy HH:MM:SS': '%b %d %Y %H:%M:%S',
    }
    
    formats_to_try = []
    if fmt_hint in format_map:
        formats_to_try.append(format_map[fmt_hint])
    
    # Add common formats
    formats_to_try.extend([
        "%d %b %Y %H:%M:%S",  # "01 Jan 2020 12:00:00"
        "%b %d %Y %H:%M:%S",  # "Jan 01 2020 12:00:00"
        "%m/%d/%Y %H:%M:%S",  # "01/01/2020 12:00:00"
        "%Y-%m-%d %H:%M:%S",  # "2020-01-01 12:00:00"
    ])
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(time_str, fmt)
            # Convert to MATLAB datenum
            ordinal = dt.toordinal()
            frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
            return ordinal + 366 + frac
        except ValueError:
            continue
    
    # If all formats fail, return 0
    return 0.0


def _genvarname(name: str) -> str:
    """MATLAB genvarname-equivalent encoding for SBE column names.

    MATLAB's readSBEcnvData calls ``convertSBEcnvVar(genvarname(columns{k}), ...)``.
    genvarname replaces every character that is not a letter, digit, or
    underscore with its character code formatted as ``0x%02X`` (uppercase hex),
    e.g. ``c0S/m`` -> ``c0S0x2Fm`` and ``flECO-AFL`` -> ``flECO0x2DAFL``. If the
    result does not start with a letter, an ``x`` is prepended.
    """
    out: list[str] = []
    for ch in name:
        if (ch.isascii() and ch.isalnum()) or ch == "_":
            out.append(ch)
        else:
            out.append(f"0x{ord(ch):02X}")
    result = "".join(out)
    if result and not (result[0].isascii() and result[0].isalpha()) and result[0] != "_":
        result = "x" + result
    return result


def parse_cnv_to_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
    instrument_model: str,
) -> IMOSDataset:
    """Parse a Sea-Bird CNV file into an IMOSDataset.

    Uses native Python CNV parser with IMOS variable name conversion.
    
    Mirrors MATLAB workflow:
    1. readSBEcnv() - Parse CNV file structure
    2. parseInstrumentHeader() - Extract instrument metadata
    3. parseProcessedHeader() - Extract processing metadata
    4. readSBEcnvData() + convertSBEcnvVar() - Parse data and convert variable names
    5. genTimestamps() - Generate TIME if not present
    6. Add scaffold variables and metadata
    """

    # Read file content
    content = source_file.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    # Separate header sections — mirrors MATLAB readSBEcnv.m exactly:
    #   iStar = strncmp(allLines, '*', 1);
    #   instHeaderLines = allLines(iStar);
    #   iHash = strncmp(allLines, '#', 1);
    #   procHeaderLines = allLines(iHash);
    #   iData = ~(iStar | iHash);
    #   dataLines = allLines(iData);
    inst_header_lines: list[str] = []
    proc_header_lines: list[str] = []
    data_lines: list[str] = []
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith("*"):
            inst_header_lines.append(line_stripped)
        elif line_stripped.startswith("#"):
            proc_header_lines.append(line_stripped)
        else:
            data_lines.append(line_stripped)

    # Parse headers
    inst_header = parse_instrument_header(inst_header_lines, mode)
    proc_header = _parse_processed_header(proc_header_lines)

    # Parse data section
    variable_names = proc_header.get('columns', [])
    bad_flag = proc_header.get('badFlag', -9.990e-29)
    
    if not variable_names:
        raise ValueError(f"No variables found in CNV header: {source_file}")

    # Parse data rows — mirrors MATLAB: dataLines = strjoin(dataLines, ' ');
    # dataLines = textscan(dataLines, format);
    data_rows: list[list[float]] = []
    for line_stripped in data_lines:
        if not line_stripped:
            continue
        
        try:
            # Split by whitespace and convert to floats
            values = [float(x) for x in line_stripped.split()]
            if len(values) == len(variable_names):
                # Convert bad_flag values to NaN (MATLAB uses exact equality:
                # d(d == procHeader.badFlag) = nan)
                values = [np.nan if v == bad_flag else v for v in values]
                data_rows.append(values)
        except ValueError:
            continue

    if not data_rows:
        raise ValueError(f"No valid data rows found in {source_file}")

    # Convert to numpy array and build data dict
    data_array = np.array(data_rows)
    data_dict: dict[str, np.ndarray] = {}
    comment_dict: dict[str, str] = {}
    
    # Determine time offset for TIME variable conversions
    # Mirrors MATLAB readSBEcnvData.m exactly:
    #   if isfield(instHeader, 'castDate')
    #       castDate = instHeader.castDate;
    #   else
    #       if isfield(procHeader,'startTime')
    #           castDate = procHeader.startTime;
    #       else
    #           castDate = 0;
    #       end
    #   end
    if 'castDate' in inst_header:
        cast_date = inst_header['castDate']
        time_offset = cast_date[0] if isinstance(cast_date, list) else cast_date
    elif 'startTime' in proc_header:
        time_offset = proc_header['startTime']
    else:
        time_offset = 0.0
    
    # Convert variables using convert_sbe_var (builds data_dict)
    for idx, raw_name in enumerate(variable_names):
        imos_name, converted_data, comment = convert_sbe_var(
            name=_genvarname(raw_name),
            data=data_array[:, idx],
            time_offset=time_offset,
            mode=mode,
            inst_header=inst_header,
            proc_header=proc_header,
        )
        
        if not imos_name:
            continue
        
        # Handle duplicate variable names (append _1, _2, etc for timeSeries mode)
        final_name = imos_name
        if mode == 'timeSeries' and imos_name in data_dict:
            count = 1
            while f"{imos_name}_{count}" in data_dict:
                count += 1
            final_name = f"{imos_name}_{count}"
        elif mode == 'profile':
            # In profile mode, last occurrence wins (overwrite)
            pass
        
        data_dict[final_name] = converted_data
        comment_dict[final_name] = comment
    
    # Generate TIME if not present
    # Mirrors MATLAB genTimestamps: checks data.TIME first, then generates
    if 'TIME' not in data_dict:
        # Generate time based on actual data length, not header predictions
        n_actual_samples = len(next(iter(data_dict.values()))) if data_dict else 0
        time_array = generate_timestamps(inst_header, n_actual_samples, data_dict=data_dict)
        data_dict['TIME'] = time_array
        comment_dict['TIME'] = 'Generated from header information'
    
    # Calculate sample interval if not in header
    if 'sampleInterval' not in inst_header and 'TIME' in data_dict:
        time_diff = np.diff(data_dict['TIME'] * 24 * 3600)  # Convert to seconds
        inst_header['instrument_sample_interval'] = float(np.median(time_diff))
    elif 'sampleInterval' in inst_header:
        inst_header['instrument_sample_interval'] = inst_header['sampleInterval']
    
    # Build dataset based on mode
    if mode == 'profile':
        dataset = _build_profile_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )
    else:  # timeSeries
        dataset = _build_timeseries_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )
    
    return dataset


def _parse_processed_header(header_lines: list[str]) -> dict[str, Any]:
    """Parse processed header lines (lines starting with '#').
    
    Mirrors MATLAB parseProcessedHeader() function.
    
    Args:
        header_lines: Lines starting with '#' from CNV file
        
    Returns:
        Dictionary with columns, nvalues, badFlag, startTime, etc.
    """
    header: dict[str, Any] = {}
    header['columns'] = []
    
    for line in header_lines:
        # Column names: # name N = varname: description
        if match := re.search(r'# name \d+ = (.+):', line):
            var_name = match.group(1).strip()
            header['columns'].append(var_name)
        
        # Number of values
        elif match := re.search(r'# nvalues = (\d+)', line):
            header['nValues'] = int(match.group(1))
        
        # Bad flag value
        elif match := re.search(r'# bad_flag = (.*)$', line):
            try:
                header['badFlag'] = float(match.group(1).strip())
            except ValueError:
                pass
        
        # Start time
        # Mirrors MATLAB SBE19Parse startExpr: capture only the date, ignoring
        # any trailing annotation like "[Instrument's time stamp, ...]".
        elif match := re.search(r'# start_time = (\w+ \d+ \d+ \d+:\d+:\d+)', line):
            time_str = match.group(1).strip()
            header['startTime'] = _parse_sbe_datetime(time_str)
        
        # Voltage channel expressions
        elif match := re.search(r'# sensor \d+ = Extrnl Volt  0  (.+)', line):
            header['volt0Expr'] = match.group(1)
        elif match := re.search(r'# sensor \d+ = Extrnl Volt  1  (.+)', line):
            header['volt1Expr'] = match.group(1)
        elif match := re.search(r'# sensor \d+ = Extrnl Volt  2  (.+)', line):
            header['volt2Expr'] = match.group(1)
        
        # Bin size
        elif match := re.search(r'# binavg_binsize = (\d+)', line):
            header['binSize'] = int(match.group(1))
    
    return header


def _build_timeseries_dataset(
    data_dict: dict[str, np.ndarray],
    comment_dict: dict[str, str],
    inst_header: dict[str, Any],
    proc_header: dict[str, Any],
    source_file: Path,
    parser_name: str,
    instrument_model: str,
) -> IMOSDataset:
    """Build timeSeries mode dataset.
    
    Args:
        data_dict: Dictionary of variable data
        comment_dict: Dictionary of variable comments
        inst_header: Parsed instrument header
        proc_header: Parsed processed header
        source_file: Source file path
        parser_name: Parser name
        instrument_model: Instrument model
        
    Returns:
        IMOSDataset for timeSeries mode
    """
    time_dim = "TIME"
    time_data = data_dict['TIME']
    
    dataset = IMOSDataset.empty()
    dataset.add_dimension(time_dim, time_data)
    
    # Add scaffold variables (scalars)
    dataset.add_variable(
        name='TIMESERIES',
        data=np.int32(1),
        dims=[],
        attrs={'long_name': 'timeSeries index', 'cf_role': 'timeseries_id'},
    )
    
    dataset.add_variable(
        name='LATITUDE',
        data=np.float64(np.nan),
        dims=[],
        attrs={'long_name': 'latitude', 'units': 'degrees_north'},
    )
    
    dataset.add_variable(
        name='LONGITUDE',
        data=np.float64(np.nan),
        dims=[],
        attrs={'long_name': 'longitude', 'units': 'degrees_east'},
    )
    
    dataset.add_variable(
        name='NOMINAL_DEPTH',
        data=np.float64(np.nan),
        dims=[],
        attrs={'long_name': 'nominal depth', 'units': 'meters', 'positive': 'down'},
    )
    
    # Add data variables (skip TIME — mirrors MATLAB: strncmp('TIME', vars{k}, 4))
    coordinates = 'TIME LATITUDE LONGITUDE NOMINAL_DEPTH'
    for var_name, var_data in data_dict.items():
        if var_name[:4] == 'TIME':
            continue  # Skip any variable starting with 'TIME' (mirrors MATLAB strncmp)
        
        attrs: dict[str, Any] = {'coordinates': coordinates}
        if var_name in comment_dict and comment_dict[var_name]:
            attrs['comment'] = comment_dict[var_name]
        
        # Add applied_offset for PRES_REL (mirrors MATLAB: -14.7*0.689476)
        if var_name.startswith('PRES_REL'):
            attrs['applied_offset'] = np.float32(-14.7 * 0.689476)
        
        dataset.add_variable(
            name=var_name,
            data=var_data,
            dims=[time_dim],
            attrs=attrs,
        )
    
    # Set global attributes
    _set_global_attributes(dataset, inst_header, proc_header, source_file, parser_name, instrument_model, 'timeSeries')
    
    return dataset


def _build_profile_dataset(
    data_dict: dict[str, np.ndarray],
    comment_dict: dict[str, str],
    inst_header: dict[str, Any],
    proc_header: dict[str, Any],
    source_file: Path,
    parser_name: str,
    instrument_model: str,
) -> IMOSDataset:
    """Build profile mode dataset with ascent/descent detection.
    
    Mirrors MATLAB profile mode implementation.
    
    Args:
        data_dict: Dictionary of variable data
        comment_dict: Dictionary of variable comments
        inst_header: Parsed instrument header
        proc_header: Parsed processed header
        source_file: Source file path
        parser_name: Parser name
        instrument_model: Instrument model
        
    Returns:
        IMOSDataset for profile mode
    """
    # Check for vertical binning
    if 'binSize' not in proc_header:
        print(f"Warning: {source_file} has not been vertically binned as per IMOS CTD Processing Procedures")
    
    # Find depth/pressure variable
    depth_var = None
    depth_comment = ''
    
    if 'DEPTH' in data_dict:
        depth_var = 'DEPTH'
        z_data = data_dict['DEPTH']
    elif 'PRES_REL' in data_dict:
        z_data = data_dict['PRES_REL']
        pres_comment = ('relative pressure measurements (calibration offset usually performed to balance current '
                       'atmospheric pressure and acute sensor precision at a deployed depth)')
        depth_comment = f'Depth computed from {pres_comment}, assuming 1dbar ~= 1m.'
    else:
        raise ValueError('No pressure or depth information in this file to use it in profile mode')
    
    # Detect ascent/descent
    n_data = len(z_data)
    z_max = np.nanmax(z_data)
    pos_z_max = np.where(z_data == z_max)[0][-1]  # Last occurrence of max
    
    # Descending: 0 to pos_z_max, Ascending: pos_z_max+1 to end
    is_descending = np.zeros(n_data, dtype=bool)
    is_descending[:pos_z_max + 1] = True
    
    n_descending = np.sum(is_descending)
    n_ascending = np.sum(~is_descending)
    max_z = max(n_descending, n_ascending)
    
    # Build dataset
    dataset = IMOSDataset.empty()
    time_data = data_dict['TIME']
    
    if n_ascending == 0:
        # Single profile (descending only)
        dataset.add_dimension('DEPTH', z_data)
        
        dataset.add_variable(
            name='PROFILE',
            data=np.int32(1),
            dims=[],
            attrs={'long_name': 'profile index'},
        )
        
        # TIME variable (scalar - first time value)
        dataset.add_variable(
            name='TIME',
            data=time_data[0],
            dims=[],
            attrs={'comment': 'First value over profile measurement.'},
        )
        
        # DIRECTION variable (scalar)
        dataset.add_variable(
            name='DIRECTION',
            data='D',
            dims=[],
            attrs={'long_name': 'profile direction'},
        )
        
        # Position variables (scalars)
        dataset.add_variable(name='LATITUDE', data=np.float64(np.nan), dims=[], attrs={'units': 'degrees_north'})
        dataset.add_variable(name='LONGITUDE', data=np.float64(np.nan), dims=[], attrs={'units': 'degrees_east'})
        dataset.add_variable(name='BOT_DEPTH', data=np.float32(np.nan), dims=[],
                           attrs={'comment': 'Bottom depth measured by ship-based acoustic sounder at time of CTD cast.'})
        
        # Data variables (1D along DEPTH)
        for var_name, var_data in data_dict.items():
            if var_name in ['TIME', 'DEPTH']:
                continue
            
            attrs: dict[str, Any] = {'coordinates': 'TIME LATITUDE LONGITUDE DEPTH'}
            if var_name in comment_dict and comment_dict[var_name]:
                attrs['comment'] = comment_dict[var_name]
            
            if var_name.startswith('PRES_REL'):
                attrs['applied_offset'] = np.float32(-14.7 * 0.689476)
            
            dataset.add_variable(name=var_name, data=var_data[is_descending], dims=['DEPTH'], attrs=attrs)
    
    else:
        # Multi-profile (descending + ascending)
        print(f"Warning: {source_file} is not IMOS CTD profile compliant (contains ascent)")
        
        dataset.add_dimension('MAXZ', np.arange(1, max_z + 1))
        dataset.add_dimension('PROFILE', np.array([1, 2]))
        
        # TIME variable (2-element array: [descending_start, ascending_start])
        time_desc = time_data[is_descending][0]
        time_asc = time_data[~is_descending][0]
        dataset.add_variable(
            name='TIME',
            data=np.array([time_desc, time_asc]),
            dims=['PROFILE'],
            attrs={'comment': 'First value over profile measurement.'},
        )
        
        # DIRECTION variable (2-element array)
        dataset.add_variable(
            name='DIRECTION',
            data=np.array(['D', 'A'], dtype='<U1'),
            dims=['PROFILE'],
            attrs={'long_name': 'profile direction'},
        )
        
        # Position variables (2-element arrays)
        dataset.add_variable(name='LATITUDE', data=np.array([np.nan, np.nan]), dims=['PROFILE'], attrs={'units': 'degrees_north'})
        dataset.add_variable(name='LONGITUDE', data=np.array([np.nan, np.nan]), dims=['PROFILE'], attrs={'units': 'degrees_east'})
        dataset.add_variable(name='BOT_DEPTH', data=np.array([np.nan, np.nan]), dims=['PROFILE'],
                           attrs={'comment': 'Bottom depth measured by ship-based acoustic sounder at time of CTD cast.'})
        
        # DEPTH variable if not present (2D: MAXZ x PROFILE)
        if depth_var is None:
            depth_desc = np.pad(z_data[is_descending], (0, max_z - n_descending), constant_values=np.nan)
            depth_asc = np.pad(z_data[~is_descending], (0, max_z - n_ascending), constant_values=np.nan)
            dataset.add_variable(
                name='DEPTH',
                data=np.column_stack([depth_desc, depth_asc]),
                dims=['MAXZ', 'PROFILE'],
                attrs={'comment': depth_comment, 'axis': 'Z'},
            )
        
        # Data variables (2D: MAXZ x PROFILE)
        for var_name, var_data in data_dict.items():
            if var_name in ['TIME']:
                continue
            # Mirrors MATLAB: if strcmpi('DEPTH', vars{k}) && (nA == 0), continue; end
            if var_name == 'DEPTH' and n_ascending == 0:
                continue
            
            attrs = {'coordinates': 'TIME LATITUDE LONGITUDE DEPTH'}
            if var_name in comment_dict and comment_dict[var_name]:
                attrs['comment'] = comment_dict[var_name]
            
            if var_name.startswith('PRES_REL'):
                attrs['applied_offset'] = np.float32(-14.7 * 0.689476)
            
            # Pad data to MAXZ dimension
            data_desc = np.pad(var_data[is_descending], (0, max_z - n_descending), constant_values=np.nan)
            data_asc = np.pad(var_data[~is_descending], (0, max_z - n_ascending), constant_values=np.nan)
            
            dataset.add_variable(
                name=var_name,
                data=np.column_stack([data_desc, data_asc]),
                dims=['MAXZ', 'PROFILE'],
                attrs=attrs,
            )
    
    # Set global attributes
    _set_global_attributes(dataset, inst_header, proc_header, source_file, parser_name, instrument_model, 'profile')
    
    return dataset


def _set_global_attributes(
    dataset: IMOSDataset,
    inst_header: dict[str, Any],
    proc_header: dict[str, Any],
    source_file: Path,
    parser_name: str,
    instrument_model: str,
    mode: str,
) -> None:
    """Set global attributes from headers.
    
    Args:
        dataset: Dataset to modify
        inst_header: Instrument header dict
        proc_header: Processed header dict
        source_file: Source file path
        parser_name: Parser name
        instrument_model: Instrument model
        mode: 'timeSeries' or 'profile'
    """
    dataset.set_attrs(
        {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": inst_header.get('instrument_make', "Seabird"),
            "instrument_model": inst_header.get('instrument_model', instrument_model),
            "instrument_firmware": inst_header.get('instrument_firmware', ''),
            "instrument_serial_no": inst_header.get('instrument_serial_no', ''),
            "instrument_sample_interval": inst_header.get('instrument_sample_interval', np.nan),
            "parser": parser_name,
            "source_format": "cnv",
        }
    )
    
    # Add additional metadata from headers
    for key, value in inst_header.items():
        if key not in ['instrument_make', 'instrument_model', 'instrument_firmware', 'instrument_serial_no', 'instrument_sample_interval']:
            dataset.dataset.attrs[f"inst_header_{key}"] = _safe_attr(value)
    
    for key, value in proc_header.items():
        if key != 'columns':  # Don't store column list as attribute
            dataset.dataset.attrs[f"proc_header_{key}"] = _safe_attr(value)


def _safe_attr(value: Any) -> Any:
    """Convert value to NetCDF-safe attribute type."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        # Convert lists to comma-separated strings for NetCDF attributes
        return ', '.join(str(v) for v in value)
    return str(value)


def _parse_sbe_datetime(time_str: str) -> float:
    """Parse SeaBird datetime string to MATLAB datenum.
    
    Args:
        time_str: DateTime string from CNV file (e.g., "mmm dd yyyy HH:MM:SS")
        
    Returns:
        MATLAB datenum (days since 0000-01-01)
    """
    # Try common SeaBird datetime formats
    formats = [
        "%b %d %Y %H:%M:%S",  # "Jan 01 2020 12:00:00"
        "%m/%d/%Y %H:%M:%S",  # "01/01/2020 12:00:00"
        "%Y-%m-%d %H:%M:%S",  # "2020-01-01 12:00:00"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            # Convert to MATLAB datenum
            ordinal = dt.toordinal()
            frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
            return ordinal + 366 + frac
        except ValueError:
            continue
    
    # If all formats fail, return 0
    return 0.0


def parse_sbe3x_asc_to_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
    instrument_model: str,
    variable_layout: Sequence[str] = ("TEMP", "CNDC", "PRES_REL", "PSAL"),
) -> IMOSDataset:
    """Parse Sea-Bird SBE3x-style ASCII data rows.

    Full port of MATLAB SBE3x.m. The instrument header (lines starting with
    ``*``) is parsed to extract instrument model/firmware/serial number,
    calibration coefficients, sensor calibration dates and pressure sensor
    metadata, and to determine which variables are present in the data
    (temperature, conductivity, pressure, salinity). When no header is present
    the column count of the first data line is used (mirrors MATLAB), assuming
    the SBE37 column order temperature, conductivity, pressure, salinity.

    The ``variable_layout`` argument is retained for backwards compatibility but
    is no longer used to drive column detection (the header / column-count
    logic matches MATLAB instead).
    """
    # IMOS-compliant variable names (mirrors SBE3x.m constants)
    TEMPERATURE_NAME = "TEMP"
    CONDUCTIVITY_NAME = "CNDC"
    PRESSURE_NAME = "PRES_REL"
    SALINITY_NAME = "PSAL"

    # Regular expressions mirroring SBE3x.m
    header_expr = re.compile(r'^\*\s*(SBE\S+)\s+V\s+(\S+)\s+(\d+)$')
    cal_coeff_expr = re.compile(r'^\*\s*(\w+)\s*=\s*(\S+)\s*$')
    sensor_cal_expr = re.compile(r'^\*\s*(\w+):\s*(.+?)\s*$')
    salinity_expr = re.compile(r'^\*\s*output salinity', re.IGNORECASE)
    pressure_cal_expr = re.compile(
        r'^\*\s*pressure\s+S/N\s+(\d+),\s*range\s*=\s*(\d+)\s+psia:?\s*(.+?)\s*$'
    )

    inst_header: dict[str, Any] = {}
    proc_header: dict[str, Any] = {}
    # MATLAB SBE3x.m sets this specific make string (differs from the
    # 'Seabird' used by the .cnv/.hex/.tid parsers).
    inst_header["instrument_make"] = "Sea-bird Electronics"

    read_temp = False
    read_cond = False
    read_pres = False
    read_sal = False

    lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    data_lines: list[str] = []
    in_header = True
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # Header section: empty, or lines starting with '*' or 's'
        if in_header and (not stripped or stripped[0] in ("*", "s")):
            if not stripped or stripped[0] == "s":
                # blank or echoed command line - skip (mirrors MATLAB)
                continue

            # 1. calibration coefficient line (name = value)
            m = cal_coeff_expr.match(stripped)
            if m:
                key, value = m.group(1), m.group(2)
                if key != "FileName":
                    try:
                        inst_header[key] = float(value)
                    except ValueError:
                        inst_header[key] = value
                continue

            # 2. sensor calibration date (name: value)
            m = sensor_cal_expr.match(stripped)
            if m:
                sensor, cal_date = m.group(1), m.group(2).strip()
                inst_header[f"{sensor}_calibration_date"] = cal_date
                if sensor == "temperature":
                    read_temp = True
                elif sensor == "conductivity":
                    read_cond = True
                continue

            # 3. pressure sensor info
            m = pressure_cal_expr.match(stripped)
            if m:
                read_pres = True
                inst_header["pressure_serial_no"] = m.group(1).strip()
                try:
                    inst_header["pressure_range_psia"] = float(m.group(2))
                except ValueError:
                    inst_header["pressure_range_psia"] = m.group(2)
                inst_header["pressure_calibration_date"] = m.group(3).strip()
                continue

            # 4. instrument info (model / firmware / serial)
            m = header_expr.match(stripped)
            if m:
                inst_header["instrument_model"] = m.group(1)
                inst_header["instrument_firmware"] = m.group(2)
                inst_header["instrument_serial_no"] = m.group(3)

            # 5. salinity output flag
            if salinity_expr.match(stripped):
                read_sal = True

            continue

        # First non-header line marks the start of the data section
        in_header = False
        if stripped:
            data_lines.append(stripped)

    # Determine the active variables / column order
    if read_temp or read_cond or read_pres or read_sal:
        active_vars: list[str] = []
        if read_temp:
            active_vars.append(TEMPERATURE_NAME)
        if read_cond:
            active_vars.append(CONDUCTIVITY_NAME)
        if read_pres:
            active_vars.append(PRESSURE_NAME)
        if read_sal:
            active_vars.append(SALINITY_NAME)
    else:
        # Headerless file: infer columns from the first data line (mirrors
        # MATLAB SBE3x.m, which assumes the SBE37 column order).
        if not data_lines:
            raise ValueError(f"No supported SBE3x ASCII samples found in {source_file}")
        n_col = data_lines[0].count(",") + 1
        column_map = {
            3: [TEMPERATURE_NAME],
            4: [TEMPERATURE_NAME, CONDUCTIVITY_NAME],
            5: [TEMPERATURE_NAME, CONDUCTIVITY_NAME, PRESSURE_NAME],
            6: [TEMPERATURE_NAME, CONDUCTIVITY_NAME, PRESSURE_NAME, SALINITY_NAME],
        }
        if n_col not in column_map:
            raise ValueError(f"Unsupported SBE3x ASCII file format ({n_col} columns)")
        active_vars = column_map[n_col]

    n_active = len(active_vars)
    values_by_var: dict[str, list[float]] = {name: [] for name in active_vars}
    time_values: list[float] = []

    for line in data_lines:
        parts = [part.strip() for part in line.split(",")]
        # Need n_active numeric columns + date + time
        if len(parts) < n_active + 2:
            continue
        try:
            numeric = [float(token) for token in parts[:n_active]]
            dt = datetime.strptime(
                f"{parts[n_active]}, {parts[n_active + 1]}", "%d %b %Y, %H:%M:%S"
            )
        except ValueError:
            continue

        for var_name, value in zip(active_vars, numeric):
            values_by_var[var_name].append(value)
        time_values.append(_datetime_to_matlab_datenum(dt))

    if not time_values:
        raise ValueError(f"No supported SBE3x ASCII samples found in {source_file}")

    # Build data_dict and comment_dict for IMOS compliance
    data_dict: dict[str, np.ndarray] = {}
    comment_dict: dict[str, str] = {}

    data_dict["TIME"] = np.asarray(time_values, dtype=float)
    comment_dict["TIME"] = ""

    for var_name in active_vars:
        data_dict[var_name] = np.asarray(values_by_var[var_name], dtype=float)
        comment_dict[var_name] = ""

    # Sample interval (mirrors median(diff(time*24*3600)))
    if len(time_values) > 1:
        time_diff = np.diff(data_dict["TIME"] * 24 * 3600)
        inst_header["instrument_sample_interval"] = float(np.median(time_diff))
    else:
        inst_header["instrument_sample_interval"] = 0.0

    # Build dataset using the shared IMOS builders
    if mode == "profile":
        dataset = _build_profile_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )
    else:  # timeSeries
        dataset = _build_timeseries_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )

    return dataset


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac


def parse_sbe56_csv_to_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
    instrument_model: str,
) -> IMOSDataset:
    """Parse Sea-Bird SBE56 CSV export data.

    Expected columns include DATE, TIME, and TEMPERATURE (case-insensitive).
    
    Mirrors MATLAB readSBE56csv with full IMOS compliance.
    """

    rows = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_lines = [line for line in rows if line.strip().startswith("%")]
    data_lines = [line for line in rows if line.strip() and not line.strip().startswith("%")]

    if not data_lines:
        raise ValueError(f"No CSV data rows found in {source_file}")

    reader = csv.DictReader(data_lines)
    if reader.fieldnames is None:
        raise ValueError(f"Unable to detect CSV header row in {source_file}")

    normalized_fields = {_normalize_csv_field(name): name for name in reader.fieldnames}
    required = ["DATE", "TIME", "TEMPERATURE"]
    missing = [field for field in required if field not in normalized_fields]
    if missing:
        raise ValueError(f"SBE56 CSV missing required columns: {', '.join(missing)}")

    date_key = normalized_fields["DATE"]
    time_key = normalized_fields["TIME"]
    temp_key = normalized_fields["TEMPERATURE"]

    times: list[float] = []
    temps: list[float] = []
    for row in reader:
        try:
            temp = float((row.get(temp_key) or "").strip().strip('"'))
            dt = _parse_sbe56_datetime(
                date_text=(row.get(date_key) or "").strip().strip('"'),
                time_text=(row.get(time_key) or "").strip().strip('"'),
            )
        except ValueError:
            continue

        temps.append(temp)
        times.append(_datetime_to_matlab_datenum(dt))

    if not temps:
        raise ValueError(f"No valid SBE56 CSV samples found in {source_file}")

    # Build data_dict and comment_dict for IMOS compliance
    data_dict: dict[str, np.ndarray] = {}
    comment_dict: dict[str, str] = {}
    
    data_dict['TIME'] = np.asarray(times, dtype=float)
    data_dict['TEMP'] = np.asarray(temps, dtype=float)
    comment_dict['TIME'] = ''
    comment_dict['TEMP'] = ''
    
    # Parse instrument metadata from CSV header
    inst_header: dict[str, Any] = {}
    proc_header: dict[str, Any] = {}
    
    for line in header_lines:
        if "=" not in line:
            continue
        key, value = line.lstrip("%").split("=", 1)
        key_clean = key.strip()
        value_clean = value.strip()
        
        if "Instrument type" in key_clean:
            inst_header['instrument_model'] = value_clean
        elif "Serial Number" in key_clean:
            inst_header['instrument_serial_no'] = value_clean
        elif "Firmware Version" in key_clean:
            inst_header['instrument_firmware'] = value_clean
    
    # Calculate sample interval
    if len(times) > 1:
        time_diff = np.diff(np.asarray(times) * 24 * 3600)  # Convert to seconds
        inst_header['instrument_sample_interval'] = float(np.median(time_diff))
    else:
        inst_header['instrument_sample_interval'] = 0.0
    
    # Build dataset using the same function as CNV parser for IMOS compliance
    if mode == 'profile':
        dataset = _build_profile_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )
    else:  # timeSeries
        dataset = _build_timeseries_dataset(
            data_dict, comment_dict, inst_header, proc_header, source_file, parser_name, instrument_model
        )

    return dataset


def _normalize_csv_field(field: str) -> str:
    return "".join(char for char in field.upper() if char.isalnum())


def _parse_sbe56_datetime(date_text: str, time_text: str) -> datetime:
    date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    time_formats = ["%H:%M:%S.%f", "%H:%M:%S"]
    for date_fmt in date_formats:
        for time_fmt in time_formats:
            try:
                return datetime.strptime(f"{date_text} {time_text}", f"{date_fmt} {time_fmt}")
            except ValueError:
                continue
    raise ValueError("Unsupported SBE56 date/time format")

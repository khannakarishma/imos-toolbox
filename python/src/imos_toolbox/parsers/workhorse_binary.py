"""Binary PD0 format reader for Workhorse ADCP files.

Mirrors MATLAB readWorkhorseEnsembles.m implementation.
Reads and validates ensembles from Teledyne RDI Workhorse ADCP binary files.

Author: Kiro AI Assistant
Based on MATLAB implementation by Paul McCarthy, Charles James, Guillaume Galibert
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import numpy as np


def _to_int16(value: int) -> int:
    """Interpret a 16-bit value as a signed two's complement integer."""
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def _to_int32(value: int) -> int:
    """Interpret a 32-bit value as a signed two's complement integer."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


def read_workhorse_ensembles(filename: Path) -> dict[str, Any]:
    """Read all ensembles from a Workhorse ADCP binary file.
    
    Mirrors MATLAB readWorkhorseEnsembles.m function.
    
    Parses binary PD0 format file structure:
    - Header: Ensemble information (size/contents)
    - Fixed Leader Data: ADCP configuration, serial number
    - Variable Leader Data: Time, temperature, salinity
    - Velocity: Current velocities for each depth cell
    - Correlation Magnitude: Echo autocorrelation magnitude
    - Echo Intensity: Echo intensity data for each beam
    - Percent Good: Percentage of good data for each cell
    - Bottom Track Data: (optional)
    
    Args:
        filename: Path to binary PD0 file
        
    Returns:
        Dictionary with ensemble data:
            - fixedLeader: Fixed leader data (dict)
            - variableLeader: Variable leader data (dict)
            - velocity: Velocity data (dict)
            - correlationMagnitude: Correlation magnitude data (dict)
            - echoIntensity: Echo intensity data (dict)
            - percentGood: Percent good data (dict)
            
    Raises:
        ValueError: If no valid ensembles found
    """
    # Read entire file into memory
    data = np.fromfile(filename, dtype=np.uint8)
    
    if len(data) == 0:
        raise ValueError(f"File {filename} is empty")
    
    # Ensemble start markers (mirrors MATLAB headerID and dataSourceID)
    HEADER_ID = 127  # 0x7F
    DATA_SOURCE_ID = 127  # 0x7F
    
    # Find potential ensemble starts
    # Mirrors: idh = data(1:end-1) == headerID; ids = data(2:end) == dataSourceID
    idh = data[:-1] == HEADER_ID
    ids = data[1:] == DATA_SOURCE_ID
    idx = np.where(idh & ids)[0]
    
    if len(idx) == 0:
        raise ValueError(f"No ensemble markers found in {filename}")
    
    # Get number of bytes in each ensemble (mirrors nBytes extraction)
    # Bytes at idx+2 and idx+3 contain ensemble length (little-endian uint16)
    bpe = np.column_stack([data[idx + 2], data[idx + 3]])
    # Convert to int to avoid uint8/uint16 overflow issues
    n_bytes = np.array([int(bpe[i, 0]) + (int(bpe[i, 1]) << 8) for i in range(len(bpe))])
    
    # Total length including checksum
    n_len = n_bytes + 2
    len_data = len(data)
    
    # Remove out-of-bounds ensembles (mirrors oob = (idx+nLen-1) > lenData)
    oob = (idx + n_len - 1) >= len_data
    idx = idx[~oob]
    n_bytes = n_bytes[~oob]
    n_len = n_len[~oob]
    
    # Verify checksums (mirrors checksum validation)
    given_crc = np.zeros(len(idx), dtype=np.int64)
    for i, (start, length) in enumerate(zip(idx, n_len)):
        checksum_pos = start + length - 2
        given_crc[i] = int(data[checksum_pos]) + (int(data[checksum_pos + 1]) << 8)
    
    # Calculate checksums (mirrors calcCrc computation)
    calc_crc = np.zeros(len(idx), dtype=np.int64)
    for i, (start, length) in enumerate(zip(idx, n_bytes)):
        ensemble_data = data[start:start + length]
        calc_crc[i] = int(np.sum(ensemble_data.astype(np.uint32))) & 0xFFFF
    
    # Keep only good ensembles (mirrors good = (calcCrc == givenCrc))
    good = calc_crc == given_crc
    idx = idx[good]
    n_bytes = n_bytes[good]
    
    if len(idx) == 0:
        raise ValueError(f"No ensembles passed checksum validation in {filename}")
    
    # Verify ensemble spacing (mirrors didx check)
    didx = np.diff(np.append(idx, len_data)) - 2
    spacing_ok = didx == n_bytes
    idx = idx[spacing_ok]
    n_bytes = n_bytes[spacing_ok]
    
    if len(idx) == 0:
        raise ValueError(f"No ensembles have correct spacing in {filename}")
    
    # Parse all ensembles
    ensembles: dict[str, Any] = {
        'fixedLeader': {},
        'variableLeader': {},
        'velocity': {},
        'correlationMagnitude': {},
        'echoIntensity': {},
        'percentGood': {},
        'bottomTrack': {},  # Bottom track data
    }
    
    # Pass 1: parse all fixed leaders so we can compute the modal numCells.
    for ensemble_idx, (start, length) in enumerate(zip(idx, n_bytes)):
        ensemble_data = data[start:start + length]
        _parse_fixed_leader_for_ensemble(
            ensemble_data, ensemble_idx, ensembles['fixedLeader']
        )
    
    # MATLAB uses a single static nCells = mode(numCells) for all sections.
    num_cells_arr = np.array(ensembles['fixedLeader']['numCells'])
    if num_cells_arr.size:
        vals, counts = np.unique(num_cells_arr, return_counts=True)
        mode_num_cells = int(vals[int(np.argmax(counts))])
    else:
        mode_num_cells = 0
    
    # Pass 2: parse the remaining sections using the modal numCells.
    for ensemble_idx, (start, length) in enumerate(zip(idx, n_bytes)):
        ensemble_data = data[start:start + length]
        _parse_ensemble_sections(
            ensemble_data, ensemble_idx, ensembles, mode_num_cells
        )
    
    return ensembles


def _iter_section_offsets(data: np.ndarray) -> list[int]:
    """Return the byte offset of each data-type section within an ensemble."""
    n_data_types = int(data[5])
    offsets = []
    for i in range(n_data_types):
        offset_pos = 6 + (i * 2)
        offset = int(data[offset_pos]) + (int(data[offset_pos + 1]) << 8)
        offsets.append(offset)
    return offsets


def _parse_fixed_leader_for_ensemble(
    data: np.ndarray,
    ensemble_idx: int,
    fixed_leader: dict[str, Any],
) -> None:
    """Locate and parse only the Fixed Leader section of an ensemble."""
    for offset in _iter_section_offsets(data):
        data_id = int(data[offset]) + (int(data[offset + 1]) << 8)
        if data_id == 0x0000:  # Fixed Leader Data
            _parse_fixed_leader(data[offset:], ensemble_idx, fixed_leader)
            break


def _parse_ensemble_sections(
    data: np.ndarray,
    ensemble_idx: int,
    ensembles: dict[str, Any],
    num_cells: int,
) -> None:
    """Parse the non-fixed-leader sections of an ensemble.
    
    Uses the modal num_cells (mirrors MATLAB nCells = mode(numCells)) so that
    velocity/correlation/echo/percent-good arrays are rectangular even when an
    individual ensemble reports a different cell count.
    """
    for offset in _iter_section_offsets(data):
        data_id = int(data[offset]) + (int(data[offset + 1]) << 8)
        
        if data_id == 0x0000:  # Fixed Leader Data - already parsed in pass 1
            continue
        elif data_id == 0x0080:  # Variable Leader Data
            _parse_variable_leader(data[offset:], ensemble_idx, ensembles['variableLeader'])
        elif data_id == 0x0100:  # Velocity Data
            _parse_velocity(data[offset:], ensemble_idx, ensembles['velocity'], num_cells)
        elif data_id == 0x0200:  # Correlation Magnitude Data
            _parse_correlation_magnitude(data[offset:], ensemble_idx, ensembles['correlationMagnitude'], num_cells)
        elif data_id == 0x0300:  # Echo Intensity Data
            _parse_echo_intensity(data[offset:], ensemble_idx, ensembles['echoIntensity'], num_cells)
        elif data_id == 0x0400:  # Percent Good Data
            _parse_percent_good(data[offset:], ensemble_idx, ensembles['percentGood'], num_cells)
        elif data_id == 0x0600:  # Bottom Track Data
            _parse_bottom_track(data[offset:], ensemble_idx, ensembles['bottomTrack'])


def _parse_fixed_leader(data: np.ndarray, idx: int, fixed_leader: dict) -> None:
    """Parse Fixed Leader Data section.
    
    Mirrors MATLAB parseFixedLeader logic.
    Contains ADCP configuration, serial number, etc.
    """
    # Initialize arrays on first call
    if len(fixed_leader) == 0:
        fixed_leader['firmware_version'] = []
        fixed_leader['firmware_revision'] = []
        fixed_leader['systemConfiguration'] = []
        fixed_leader['numBeams'] = []
        fixed_leader['numCells'] = []
        fixed_leader['pingsPerEnsemble'] = []
        fixed_leader['depthCellLength'] = []
        fixed_leader['bin1Distance'] = []
        fixed_leader['xmitPulseLength'] = []
        fixed_leader['tppMinutes'] = []
        fixed_leader['tppSeconds'] = []
        fixed_leader['tppHundredths'] = []
        fixed_leader['coordTransform'] = []
        fixed_leader['headingAlignment'] = []
        fixed_leader['headingBias'] = []
        fixed_leader['sensorSource'] = []
        fixed_leader['sensorAvail'] = []
        fixed_leader['beamAngle'] = []
        fixed_leader['serialNumber'] = []
    
    # Byte offsets mirror MATLAB parseFixedLeader (idx == start of section).
    # cpuFirmwareVersion / cpuFirmwareRevision
    fixed_leader['firmware_version'].append(int(data[2]))
    fixed_leader['firmware_revision'].append(int(data[3]))
    
    # System configuration (bytes 4 (LSB) and 5 (MSB))
    system_config = int(data[4]) + (int(data[5]) << 8)
    fixed_leader['systemConfiguration'].append(system_config)
    
    # Number of beams (byte 8) and cells (byte 9)
    fixed_leader['numBeams'].append(int(data[8]))
    fixed_leader['numCells'].append(int(data[9]))
    
    # Pings per ensemble (bytes 10-11, little-endian uint16)
    fixed_leader['pingsPerEnsemble'].append(int(data[10]) + (int(data[11]) << 8))
    
    # Depth cell length (bytes 12-13, cm)
    fixed_leader['depthCellLength'].append(int(data[12]) + (int(data[13]) << 8))
    # bytes 14-15 are blankAfterTransmit (unused)
    
    # Time per ping (bytes 22-24)
    fixed_leader['tppMinutes'].append(int(data[22]))
    fixed_leader['tppSeconds'].append(int(data[23]))
    fixed_leader['tppHundredths'].append(int(data[24]))
    
    # Coordinate transformation (byte 25)
    fixed_leader['coordTransform'].append(int(data[25]))
    
    # Heading alignment (bytes 26-27, signed int16, 0.01 degrees)
    heading_align = _to_int16(int(data[26]) + (int(data[27]) << 8))
    fixed_leader['headingAlignment'].append(heading_align)
    
    # Heading bias (bytes 28-29, signed int16, 0.01 degrees)
    heading_bias = _to_int16(int(data[28]) + (int(data[29]) << 8))
    fixed_leader['headingBias'].append(heading_bias)
    
    # Sensor source (byte 30) and sensors available (byte 31)
    fixed_leader['sensorSource'].append(int(data[30]))
    fixed_leader['sensorAvail'].append(int(data[31]))
    
    # Bin 1 distance (bytes 32-33, cm) and transmit pulse length (bytes 34-35, cm)
    fixed_leader['bin1Distance'].append(int(data[32]) + (int(data[33]) << 8))
    fixed_leader['xmitPulseLength'].append(int(data[34]) + (int(data[35]) << 8))
    
    # Instrument serial number (bytes 54-57, uint32) - valid for firmware >= 16.30
    serial_num = (
        int(data[54]) + (int(data[55]) << 8)
        + (int(data[56]) << 16) + (int(data[57]) << 24)
    )
    fixed_leader['serialNumber'].append(serial_num)
    
    # Beam angle (byte 58, degrees)
    fixed_leader['beamAngle'].append(int(data[58]))


def _parse_variable_leader(data: np.ndarray, idx: int, variable_leader: dict) -> None:
    """Parse Variable Leader Data section.
    
    Mirrors MATLAB parseVariableLeader logic.
    Contains time, temperature, salinity, etc.
    """
    # Initialize arrays on first call
    if len(variable_leader) == 0:
        variable_leader['rtcYear'] = []
        variable_leader['rtcMonth'] = []
        variable_leader['rtcDay'] = []
        variable_leader['rtcHour'] = []
        variable_leader['rtcMinute'] = []
        variable_leader['rtcSecond'] = []
        variable_leader['rtcHundredths'] = []
        variable_leader['temperature'] = []
        variable_leader['salinity'] = []
        variable_leader['speedOfSound'] = []
        variable_leader['pressure'] = []
        variable_leader['heading'] = []
        variable_leader['pitch'] = []
        variable_leader['roll'] = []
        variable_leader['transducerDepth'] = []
        variable_leader['transmitVoltage'] = []
        variable_leader['transmitCurrent'] = []
        variable_leader['y2kCentury'] = []
        variable_leader['y2kYear'] = []
        variable_leader['y2kMonth'] = []
        variable_leader['y2kDay'] = []
        variable_leader['y2kHour'] = []
        variable_leader['y2kMinute'] = []
        variable_leader['y2kSecond'] = []
        variable_leader['y2kHundredth'] = []
    
    # Byte offsets mirror MATLAB parseVariableLeader (idx == start of section).
    # RTC time (bytes 4-10)
    variable_leader['rtcYear'].append(int(data[4]))
    variable_leader['rtcMonth'].append(int(data[5]))
    variable_leader['rtcDay'].append(int(data[6]))
    variable_leader['rtcHour'].append(int(data[7]))
    variable_leader['rtcMinute'].append(int(data[8]))
    variable_leader['rtcSecond'].append(int(data[9]))
    variable_leader['rtcHundredths'].append(int(data[10]))
    
    # Speed of sound (bytes 14-15, uint16, m/s)
    sound_speed = int(data[14]) + (int(data[15]) << 8)
    variable_leader['speedOfSound'].append(sound_speed)
    
    # Depth of transducer (bytes 16-17, uint16, decimeters)
    depth = int(data[16]) + (int(data[17]) << 8)
    variable_leader['transducerDepth'].append(depth)
    
    # Heading (bytes 18-19, uint16, 0.01 degrees)
    heading = int(data[18]) + (int(data[19]) << 8)
    variable_leader['heading'].append(heading)
    
    # Pitch (bytes 20-21, signed int16, 0.01 degrees)
    pitch = _to_int16(int(data[20]) + (int(data[21]) << 8))
    variable_leader['pitch'].append(pitch)
    
    # Roll (bytes 22-23, signed int16, 0.01 degrees)
    roll = _to_int16(int(data[22]) + (int(data[23]) << 8))
    variable_leader['roll'].append(roll)
    
    # Salinity (bytes 24-25, uint16, ppt)
    salinity = int(data[24]) + (int(data[25]) << 8)
    variable_leader['salinity'].append(salinity)
    
    # Temperature (bytes 26-27, signed int16, 0.01 degrees C)
    temp = _to_int16(int(data[26]) + (int(data[27]) << 8))
    variable_leader['temperature'].append(temp)
    
    # ADC channel 0 = XMIT CURRENT (byte 34), ADC channel 1 = XMIT VOLTAGE (byte 35)
    variable_leader['transmitCurrent'].append(int(data[34]))
    variable_leader['transmitVoltage'].append(int(data[35]))
    
    # Pressure (bytes 48-51, signed int32, decapascals)
    pressure = _to_int32(
        int(data[48]) + (int(data[49]) << 8)
        + (int(data[50]) << 16) + (int(data[51]) << 24)
    )
    variable_leader['pressure'].append(pressure)
    
    # Y2K-compliant RTC time (bytes 57-64). Used for firmware > 8.35.
    variable_leader['y2kCentury'].append(int(data[57]))
    variable_leader['y2kYear'].append(int(data[58]))
    variable_leader['y2kMonth'].append(int(data[59]))
    variable_leader['y2kDay'].append(int(data[60]))
    variable_leader['y2kHour'].append(int(data[61]))
    variable_leader['y2kMinute'].append(int(data[62]))
    variable_leader['y2kSecond'].append(int(data[63]))
    variable_leader['y2kHundredth'].append(int(data[64]))


def _parse_velocity(data: np.ndarray, idx: int, velocity: dict, num_cells: int) -> None:
    """Parse Velocity Data section.
    
    Mirrors MATLAB parseVelocity function.
    Velocity data for each beam and depth cell.
    Format: signed 16-bit integers, mm/s, -32768 = bad value
    
    Args:
        data: Section data starting at velocity ID
        idx: Ensemble index
        velocity: Velocity dict to append to
        num_cells: Number of depth cells from Fixed Leader
    """
    num_beams = 4  # Typical for Workhorse
    
    # Initialize arrays on first call
    if len(velocity) == 0:
        velocity['vel1'] = []
        velocity['vel2'] = []
        velocity['vel3'] = []
        velocity['vel4'] = []
    
    # Parse velocity data (starts at byte 2, after 2-byte ID)
    # Length: 2 + numCells * nBeams * 2
    offset = 2
    vel_data = np.zeros((num_beams, num_cells), dtype=np.int16)
    
    for cell in range(num_cells):
        for beam in range(num_beams):
            # Read as little-endian signed int16
            if offset + 2 <= len(data):
                vel_value = struct.unpack('<h', bytes(data[offset:offset+2]))[0]
                vel_data[beam, cell] = vel_value
            else:
                vel_data[beam, cell] = -32768  # Bad value marker
            offset += 2
    
    velocity['vel1'].append(vel_data[0, :])
    velocity['vel2'].append(vel_data[1, :])
    velocity['vel3'].append(vel_data[2, :])
    velocity['vel4'].append(vel_data[3, :])


def _parse_correlation_magnitude(data: np.ndarray, idx: int, correlation: dict, num_cells: int) -> None:
    """Parse Correlation Magnitude Data section.
    
    Mirrors MATLAB parseX function for correlation magnitude.
    Length: 2 + numCells * nBeams * 1 byte
    """
    num_beams = 4
    
    if len(correlation) == 0:
        correlation['cor1'] = []
        correlation['cor2'] = []
        correlation['cor3'] = []
        correlation['cor4'] = []
    
    # Data starts at byte 2 (after 2-byte ID)
    offset = 2
    cor_data = np.zeros((num_beams, num_cells), dtype=np.uint8)
    
    for cell in range(num_cells):
        for beam in range(num_beams):
            if offset < len(data):
                cor_data[beam, cell] = int(data[offset])
            offset += 1
    
    correlation['cor1'].append(cor_data[0, :])
    correlation['cor2'].append(cor_data[1, :])
    correlation['cor3'].append(cor_data[2, :])
    correlation['cor4'].append(cor_data[3, :])


def _parse_echo_intensity(data: np.ndarray, idx: int, echo: dict, num_cells: int) -> None:
    """Parse Echo Intensity Data section.
    
    Mirrors MATLAB parseX function for echo intensity.
    Length: 2 + numCells * nBeams * 1 byte
    """
    num_beams = 4
    
    if len(echo) == 0:
        echo['echo1'] = []
        echo['echo2'] = []
        echo['echo3'] = []
        echo['echo4'] = []
    
    # Data starts at byte 2 (after 2-byte ID)
    offset = 2
    echo_data = np.zeros((num_beams, num_cells), dtype=np.uint8)
    
    for cell in range(num_cells):
        for beam in range(num_beams):
            if offset < len(data):
                echo_data[beam, cell] = int(data[offset])
            offset += 1
    
    echo['echo1'].append(echo_data[0, :])
    echo['echo2'].append(echo_data[1, :])
    echo['echo3'].append(echo_data[2, :])
    echo['echo4'].append(echo_data[3, :])


def _parse_percent_good(data: np.ndarray, idx: int, percent_good: dict, num_cells: int) -> None:
    """Parse Percent Good Data section.
    
    Mirrors MATLAB parseX function for percent good.
    Length: 2 + numCells * nBeams * 1 byte
    """
    num_beams = 4
    
    if len(percent_good) == 0:
        percent_good['pg1'] = []
        percent_good['pg2'] = []
        percent_good['pg3'] = []
        percent_good['pg4'] = []
    
    # Data starts at byte 2 (after 2-byte ID)
    offset = 2
    pg_data = np.zeros((num_beams, num_cells), dtype=np.uint8)
    
    for cell in range(num_cells):
        for beam in range(num_beams):
            if offset < len(data):
                pg_data[beam, cell] = int(data[offset])
            offset += 1
    
    percent_good['pg1'].append(pg_data[0, :])
    percent_good['pg2'].append(pg_data[1, :])
    percent_good['pg3'].append(pg_data[2, :])
    percent_good['pg4'].append(pg_data[3, :])


def _parse_bottom_track(data: np.ndarray, idx: int, bottom_track: dict) -> None:
    """Parse Bottom Track Data section.
    
    Mirrors MATLAB parseBottomTrack logic.
    Contains bottom track velocity, range, and correlation data.
    
    Bottom track is used for vessel-mounted ADCPs to measure velocity 
    relative to the seafloor. Not typically used for moored ADCPs.
    
    Data section is 85 bytes total.
    """
    # Initialize arrays on first call
    if len(bottom_track) == 0:
        bottom_track['bottomTrackId'] = []
        bottom_track['btPingsPerEnsemble'] = []
        bottom_track['btDelayBeforeReacquire'] = []
        bottom_track['btCorrMagMin'] = []
        bottom_track['btEvalAmpMin'] = []
        bottom_track['btPercentGoodMin'] = []
        bottom_track['btMode'] = []
        bottom_track['btErrVelMax'] = []
        bottom_track['btBeam1Range'] = []
        bottom_track['btBeam2Range'] = []
        bottom_track['btBeam3Range'] = []
        bottom_track['btBeam4Range'] = []
        bottom_track['btBeam1Vel'] = []
        bottom_track['btBeam2Vel'] = []
        bottom_track['btBeam3Vel'] = []
        bottom_track['btBeam4Vel'] = []
        bottom_track['btBeam1Corr'] = []
        bottom_track['btBeam2Corr'] = []
        bottom_track['btBeam3Corr'] = []
        bottom_track['btBeam4Corr'] = []
        bottom_track['btBeam1EvalAmp'] = []
        bottom_track['btBeam2EvalAmp'] = []
        bottom_track['btBeam3EvalAmp'] = []
        bottom_track['btBeam4EvalAmp'] = []
        bottom_track['btBeam1PercentGood'] = []
        bottom_track['btBeam2PercentGood'] = []
        bottom_track['btBeam3PercentGood'] = []
        bottom_track['btBeam4PercentGood'] = []
        bottom_track['btRefLayerMin'] = []
        bottom_track['btRefLayerNear'] = []
        bottom_track['btRefLayerFar'] = []
        bottom_track['btBeam1RefLayerVel'] = []
        bottom_track['btBeam2RefLayerVel'] = []
        bottom_track['btBeam3RefLayerVel'] = []
        bottom_track['btBeam4RefLayerVel'] = []
        bottom_track['btBeam1RefCorr'] = []
        bottom_track['btBeam2RefCorr'] = []
        bottom_track['btBeam3RefCorr'] = []
        bottom_track['btBeam4RefCorr'] = []
        bottom_track['btBeam1RefInt'] = []
        bottom_track['btBeam2RefInt'] = []
        bottom_track['btBeam3RefInt'] = []
        bottom_track['btBeam4RefInt'] = []
        bottom_track['btBeam1RefGood'] = []
        bottom_track['btBeam2RefGood'] = []
        bottom_track['btBeam3RefGood'] = []
        bottom_track['btBeam4RefGood'] = []
        bottom_track['btMaxDepth'] = []
        bottom_track['btBeam1RssiAmp'] = []
        bottom_track['btBeam2RssiAmp'] = []
        bottom_track['btBeam3RssiAmp'] = []
        bottom_track['btBeam4RssiAmp'] = []
        bottom_track['btGain'] = []
        bottom_track['btBeam1RangeMsb'] = []
        bottom_track['btBeam2RangeMsb'] = []
        bottom_track['btBeam3RangeMsb'] = []
        bottom_track['btBeam4RangeMsb'] = []
    
    # Parse fields (byte offsets from PD0 format spec)
    # Bytes 0-1: ID (should be 0x0600)
    bottom_track['bottomTrackId'].append(data[0] + (data[1] << 8))
    
    # Bytes 2-3: Pings per ensemble
    bottom_track['btPingsPerEnsemble'].append(data[2] + (data[3] << 8))
    
    # Bytes 4-5: Delay before reacquire
    bottom_track['btDelayBeforeReacquire'].append(data[4] + (data[5] << 8))
    
    # Bytes 6-9: Minimum thresholds
    bottom_track['btCorrMagMin'].append(data[6])
    bottom_track['btEvalAmpMin'].append(data[7])
    bottom_track['btPercentGoodMin'].append(data[8])
    bottom_track['btMode'].append(data[9])
    
    # Bytes 10-11: Error velocity max
    bottom_track['btErrVelMax'].append(data[10] + (data[11] << 8))
    
    # Bytes 12-15: Spare
    
    # Bytes 16-31: Range and velocity for 4 beams (2 bytes each, unsigned)
    bottom_track['btBeam1Range'].append(data[16] + (data[17] << 8))
    bottom_track['btBeam2Range'].append(data[18] + (data[19] << 8))
    bottom_track['btBeam3Range'].append(data[20] + (data[21] << 8))
    bottom_track['btBeam4Range'].append(data[22] + (data[23] << 8))
    
    # Velocity (2 bytes each, signed)
    bottom_track['btBeam1Vel'].append(np.int16(data[24] + (data[25] << 8)))
    bottom_track['btBeam2Vel'].append(np.int16(data[26] + (data[27] << 8)))
    bottom_track['btBeam3Vel'].append(np.int16(data[28] + (data[29] << 8)))
    bottom_track['btBeam4Vel'].append(np.int16(data[30] + (data[31] << 8)))
    
    # Bytes 32-43: Correlation, evaluation amplitude, percent good (1 byte each per beam)
    bottom_track['btBeam1Corr'].append(data[32])
    bottom_track['btBeam2Corr'].append(data[33])
    bottom_track['btBeam3Corr'].append(data[34])
    bottom_track['btBeam4Corr'].append(data[35])
    
    bottom_track['btBeam1EvalAmp'].append(data[36])
    bottom_track['btBeam2EvalAmp'].append(data[37])
    bottom_track['btBeam3EvalAmp'].append(data[38])
    bottom_track['btBeam4EvalAmp'].append(data[39])
    
    bottom_track['btBeam1PercentGood'].append(data[40])
    bottom_track['btBeam2PercentGood'].append(data[41])
    bottom_track['btBeam3PercentGood'].append(data[42])
    bottom_track['btBeam4PercentGood'].append(data[43])
    
    # Bytes 44-49: Reference layer (2 bytes each, unsigned)
    bottom_track['btRefLayerMin'].append(data[44] + (data[45] << 8))
    bottom_track['btRefLayerNear'].append(data[46] + (data[47] << 8))
    bottom_track['btRefLayerFar'].append(data[48] + (data[49] << 8))
    
    # Bytes 50-57: Reference layer velocity (2 bytes each, signed)
    bottom_track['btBeam1RefLayerVel'].append(np.int16(data[50] + (data[51] << 8)))
    bottom_track['btBeam2RefLayerVel'].append(np.int16(data[52] + (data[53] << 8)))
    bottom_track['btBeam3RefLayerVel'].append(np.int16(data[54] + (data[55] << 8)))
    bottom_track['btBeam4RefLayerVel'].append(np.int16(data[56] + (data[57] << 8)))
    
    # Bytes 58-69: Reference layer correlation, intensity, percent good (1 byte each per beam)
    bottom_track['btBeam1RefCorr'].append(data[58])
    bottom_track['btBeam2RefCorr'].append(data[59])
    bottom_track['btBeam3RefCorr'].append(data[60])
    bottom_track['btBeam4RefCorr'].append(data[61])
    
    bottom_track['btBeam1RefInt'].append(data[62])
    bottom_track['btBeam2RefInt'].append(data[63])
    bottom_track['btBeam3RefInt'].append(data[64])
    bottom_track['btBeam4RefInt'].append(data[65])
    
    bottom_track['btBeam1RefGood'].append(data[66])
    bottom_track['btBeam2RefGood'].append(data[67])
    bottom_track['btBeam3RefGood'].append(data[68])
    bottom_track['btBeam4RefGood'].append(data[69])
    
    # Bytes 70-71: Maximum depth
    bottom_track['btMaxDepth'].append(data[70] + (data[71] << 8))
    
    # Bytes 72-80: RSSI amplitude, gain, range MSB (1 byte each per beam)
    bottom_track['btBeam1RssiAmp'].append(data[72])
    bottom_track['btBeam2RssiAmp'].append(data[73])
    bottom_track['btBeam3RssiAmp'].append(data[74])
    bottom_track['btBeam4RssiAmp'].append(data[75])
    
    bottom_track['btGain'].append(data[76])
    
    bottom_track['btBeam1RangeMsb'].append(data[77])
    bottom_track['btBeam2RangeMsb'].append(data[78])
    bottom_track['btBeam3RangeMsb'].append(data[79])
    bottom_track['btBeam4RangeMsb'].append(data[80])
    
    # Bytes 81-84: Spare

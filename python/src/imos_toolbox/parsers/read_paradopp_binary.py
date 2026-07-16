"""Binary file reader for Nortek 'Paradopp' instruments.

Reads binary files from Nortek instruments including:
- AWAC
- Aquadopp Current Meter (Velocity)
- Aquadopp Profiler
- Aquadopp HR Profiler
- Continental
- Vector
- Vectrino

Mirrors MATLAB readParadoppBinary.m implementation.

Author: Kiro AI Assistant
Based on MATLAB implementation by Paul McCarthy, Guillaume Galibert, Simon Spagnol
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


# Known data section IDs and their sizes
# Generic sections (all instruments)
GENERIC_IDS = np.array([5, 4, 0], dtype=np.uint8)
GENERIC_SIZES = np.array([48, 224, 512], dtype=np.uint16)

# Continental sections
CONTINENTAL_IDS = np.array([36], dtype=np.uint8)
CONTINENTAL_SIZES = np.array([np.nan], dtype=np.float32)  # Variable size

# Aquadopp Velocity sections
AQUADOPP_VELOCITY_IDS = np.array([1, 6, 128], dtype=np.uint8)
AQUADOPP_VELOCITY_SIZES = np.array([42, 36, 42], dtype=np.uint16)

# Aquadopp Profiler sections
AQUADOPP_PROFILER_IDS = np.array([33, 48, 49, 42], dtype=np.uint8)
AQUADOPP_PROFILER_SIZES = np.array([np.nan, 24, 60, np.nan], dtype=np.float32)

# AWAC sections
AWAC_IDS = np.array([32, 54, 66], dtype=np.uint8)
AWAC_SIZES = np.array([np.nan, 24, np.nan], dtype=np.float32)

# Prolog sections (Signature/Vector/Vectrino)
PROLOG_IDS = np.array([96, 97, 98, 99, 101, 106], dtype=np.uint8)
PROLOG_SIZES = np.array([80, 48, np.nan, np.nan, np.nan, np.nan], dtype=np.float32)

# Sections without size field in data
NO_SIZE_IDS = np.array([16, 54, 81], dtype=np.uint8)
NO_SIZE_SIZES = np.array([24, 24, 22], dtype=np.uint16)

# Combine all known IDs and sizes
ALL_KNOWN_IDS = np.concatenate([
    GENERIC_IDS, CONTINENTAL_IDS, AQUADOPP_VELOCITY_IDS,
    AQUADOPP_PROFILER_IDS, AWAC_IDS, PROLOG_IDS
])
ALL_KNOWN_SIZES = np.concatenate([
    GENERIC_SIZES, CONTINENTAL_SIZES, AQUADOPP_VELOCITY_SIZES,
    AQUADOPP_PROFILER_SIZES, AWAC_SIZES, PROLOG_SIZES
])

# Sync byte marker
SYNC_BYTE = 165  # 0xA5


def read_paradopp_binary(filename: Path | str) -> dict[str, Any]:
    """Read binary file from Nortek Paradopp instrument.
    
    Reads all data sections from a Nortek binary file and returns them
    organized by section ID.
    
    Mirrors MATLAB readParadoppBinary.m function.
    
    Args:
        filename: Path to binary file (.wpr, .prf, etc.)
        
    Returns:
        Dictionary with section data organized by ID:
            - Id0: User configuration
            - Id4: Head configuration
            - Id5: Hardware configuration
            - Id32: AWAC velocity profile data
            - Id106: AWAC processed velocity data
            - etc.
            
    Raises:
        ValueError: If file doesn't exist or cannot be read
    """
    filename = Path(filename)
    
    if not filename.exists():
        raise ValueError(f"File {filename} does not exist")
    
    # Read entire file into memory
    data = np.fromfile(filename, dtype=np.uint8)
    
    if len(data) == 0:
        raise ValueError(f"File {filename} is empty")
    
    # Determine CPU endianness
    import sys
    cpu_endianness = 'little' if sys.byteorder == 'little' else 'big'
    
    # Find sync bytes (0xA5)
    is_sync = data == SYNC_BYTE
    
    # Check that ID following sync is known
    is_id = np.isin(data, ALL_KNOWN_IDS)
    is_sync[:-1] = is_sync[:-1] & is_id[1:]
    is_sync[-1] = False
    
    # Check size consistency
    is_sync = _validate_sync_markers(data, is_sync, cpu_endianness)
    
    # Get IDs and sizes for valid sections
    ids = data[np.roll(is_sync, 1)]
    
    # Get sizes from data (bytes 2-3 after sync)
    size_indices = np.roll(is_sync, 2) | np.roll(is_sync, 3)
    sizes_from_data = _read_uint16(data[size_indices].reshape(-1, 2), cpu_endianness) * 2  # words to bytes
    
    # Replace with known sizes for sections without size field
    for no_size_id, no_size_size in zip(NO_SIZE_IDS, NO_SIZE_SIZES):
        sizes_from_data[ids == no_size_id] = no_size_size
    
    # Read sections by type
    structures = {}
    unique_ids = np.unique(ids)
    
    for section_id in unique_ids:
        section_data = _extract_section_data(data, is_sync, ids, sizes_from_data, section_id)
        
        if section_data is None:
            continue
        
        # Parse section based on ID
        parsed_sections = _parse_section(section_data, section_id, cpu_endianness)
        
        if parsed_sections is None or len(parsed_sections) == 0:
            continue
        
        # Validate checksums
        parsed_sections = _validate_checksums(section_data, parsed_sections)
        
        if len(parsed_sections) == 0:
            continue
        
        # Store in structures dict
        field_name = f"Id{section_id}"
        structures[field_name] = parsed_sections
    
    return structures


def _validate_sync_markers(
    data: np.ndarray,
    is_sync: np.ndarray,
    cpu_endianness: str
) -> np.ndarray:
    """Validate sync markers by checking size consistency.
    
    Removes false sync detections by comparing:
    - Size from data header
    - Expected size for section type
    - Distance between sync markers
    """
    # Get IDs and expected sizes
    ids = data[np.roll(is_sync, 1)]
    
    # Get sizes from data
    size_indices = np.roll(is_sync, 2) | np.roll(is_sync, 3)
    sizes_from_data = _read_uint16(data[size_indices].reshape(-1, 2), cpu_endianness) * 2
    
    # Replace with known sizes for no-size sections
    for no_size_id, no_size_size in zip(NO_SIZE_IDS, NO_SIZE_SIZES):
        sizes_from_data[ids == no_size_id] = no_size_size
    
    # Get expected sizes
    sizes_expected = np.full(len(ids), np.nan, dtype=np.float32)
    for known_id, known_size in zip(ALL_KNOWN_IDS, ALL_KNOWN_SIZES):
        sizes_expected[ids == known_id] = known_size
    
    # Fill unknown sizes with data sizes
    unknown_mask = np.isnan(sizes_expected)
    sizes_expected[unknown_mask] = sizes_from_data[unknown_mask]
    
    # Check size consistency
    size_consistent = sizes_from_data == sizes_expected
    is_sync[is_sync] = size_consistent
    
    # Check distance between syncs matches size
    sync_positions = np.where(np.append(is_sync, True))[0]
    sizes_from_sync = np.diff(sync_positions)
    
    # Re-get sizes after filtering
    ids = data[np.roll(is_sync, 1)]
    size_indices = np.roll(is_sync, 2) | np.roll(is_sync, 3)
    sizes_from_data = _read_uint16(data[size_indices].reshape(-1, 2), cpu_endianness) * 2
    for no_size_id, no_size_size in zip(NO_SIZE_IDS, NO_SIZE_SIZES):
        sizes_from_data[ids == no_size_id] = no_size_size
    
    is_size_consistent = sizes_from_data == sizes_from_sync
    
    # Remove false syncs iteratively
    is_pair_inconsistent = np.zeros(len(is_size_consistent), dtype=bool)
    is_pair_inconsistent[1:] = (~is_size_consistent[:-1]) & (~is_size_consistent[1:])
    is_pair_inconsistent = np.append(np.diff(is_pair_inconsistent.astype(int)) != 0, False) & is_pair_inconsistent
    
    while np.any(is_pair_inconsistent):
        is_sync[is_sync] = ~is_pair_inconsistent
        
        # Recalculate
        ids = data[np.roll(is_sync, 1)]
        size_indices = np.roll(is_sync, 2) | np.roll(is_sync, 3)
        sizes_from_data = _read_uint16(data[size_indices].reshape(-1, 2), cpu_endianness) * 2
        for no_size_id, no_size_size in zip(NO_SIZE_IDS, NO_SIZE_SIZES):
            sizes_from_data[ids == no_size_id] = no_size_size
        
        sync_positions = np.where(np.append(is_sync, True))[0]
        sizes_from_sync = np.diff(sync_positions)
        is_size_consistent = sizes_from_data == sizes_from_sync
        
        is_pair_inconsistent = np.zeros(len(is_size_consistent), dtype=bool)
        is_pair_inconsistent[1:] = (~is_size_consistent[:-1]) & (~is_size_consistent[1:])
        is_pair_inconsistent = np.append(np.diff(is_pair_inconsistent.astype(int)) != 0, False) & is_pair_inconsistent
    
    # Handle remaining inconsistencies
    # Mirrors MATLAB:
    #   if any(~isSizeConsistent)
    #       iSync(iSync) = [true; isSizeConsistent(1:end-1)];
    #       if ~isSizeConsistent(end)
    #           iSync(iSync) = [true(sum(iSync)-1, 1); false];
    #       end
    #   end
    if np.any(~is_size_consistent):
        # Keep first sync, then keep where previous was consistent
        keep = np.ones(np.sum(is_sync), dtype=bool)
        keep[1:] = is_size_consistent[:-1]
        is_sync[is_sync] = keep
        
        # Handle truncated last section
        if not is_size_consistent[-1]:
            n_remaining = np.sum(is_sync)
            keep2 = np.ones(n_remaining, dtype=bool)
            keep2[-1] = False
            is_sync[is_sync] = keep2
    
    return is_sync


def _extract_section_data(
    data: np.ndarray,
    is_sync: np.ndarray,
    ids: np.ndarray,
    sizes: np.ndarray,
    section_id: int
) -> np.ndarray | None:
    """Extract all data for a specific section ID.
    
    Returns 2D array: (n_sections, section_size)
    """
    # Find sections with this ID
    id_mask = ids == section_id
    section_sizes = sizes[id_mask]
    
    # Check for varying sizes
    unique_sizes = np.unique(section_sizes)
    if len(unique_sizes) > 1:
        print(f"Warning: Section ID {section_id} (0x{section_id:02X}) has varying sizes")
        print("Cannot read with vectorized code")
        return None
    
    # Convert to int to avoid uint16 overflow in calculations
    section_size = int(unique_sizes[0])
    
    # Extract data
    sync_this_id = is_sync.copy()
    sync_this_id[is_sync] = id_mask
    
    sync_positions = np.where(sync_this_id)[0]
    
    # Expand to full sections
    for start in sync_positions:
        end = start + section_size
        if end <= len(data):
            sync_this_id[start:end] = True
    
    section_data = data[sync_this_id]
    
    # Reshape to (n_sections, section_size)
    n_sections = len(section_data) // section_size
    section_data = section_data[:n_sections * section_size].reshape(n_sections, section_size)
    
    return section_data


def _parse_section(
    data: np.ndarray,
    section_id: int,
    cpu_endianness: str
) -> list[dict] | None:
    """Parse section data based on ID.
    
    Args:
        data: Section data array (n_sections, section_size)
        section_id: Section ID
        cpu_endianness: 'little' or 'big'
        
    Returns:
        List of parsed section dictionaries
    """
    # Map section ID to parser function
    parsers = {
        0: _read_user_configuration,
        1: _read_aquadopp_velocity,
        4: _read_head_configuration,
        5: _read_hardware_configuration,
        6: _read_aquadopp_diag_header,
        16: _read_vector_velocity,
        17: _read_vector_system,
        32: _read_awac_velocity_profile,
        33: _read_aquadopp_profiler_velocity,
        36: _read_continental,
        42: _read_hr_aquadopp_profile,
        48: _read_awac_wave_data,
        49: _read_awac_wave_header,
        54: _read_awac_wave_data_suv,
        66: _read_awac_stage_data,
        80: _read_vectrino_velocity_header,
        81: _read_vectrino_velocity,
        96: _read_wave_parameter_estimates,
        97: _read_wave_band_estimates,
        98: _read_wave_energy_spectrum,
        99: _read_wave_fourier_coefficient_spectrum,
        101: _read_awac_ast,
        106: _read_awac_processed_velocity,
        128: _read_aquadopp_diagnostics,
    }
    
    parser_func = parsers.get(section_id)
    
    if parser_func is None:
        print(f"Warning: No parser for section ID {section_id} (0x{section_id:02X})")
        return None
    
    return parser_func(data, cpu_endianness)


def _validate_checksums(
    data: np.ndarray,
    sections: list[dict]
) -> list[dict]:
    """Validate checksums and remove bad sections.
    
    Mirrors MATLAB genChecksum function from readParadoppBinary.m lines 2732-2756.
    
    Checksum algorithm (from System Integrator Manual, page 52):
    1. Start with 0xB58C (46476)
    2. Add sum of odd-indexed bytes (1, 3, 5, ...)
    3. Add sum of even-indexed bytes (2, 4, 6, ...) × 256
    4. Modulo 65536
    
    Args:
        data: Raw section data (n_sections, section_size)
        sections: Parsed section dictionaries
        
    Returns:
        Filtered list with valid sections only
    """
    # Calculate checksums (exclude last 2 bytes which contain checksum itself)
    data_no_cs = data[:, :-2]
    
    # Start checksum value is 0xB58C (46476)
    checksums = np.full(len(data), 46476, dtype=np.int64)
    
    # Sum odd bytes (indices 0, 2, 4, ...) 
    data_odd = data_no_cs[:, 0::2].astype(np.int64)
    checksums += np.sum(data_odd, axis=1)
    
    # Sum even bytes (indices 1, 3, 5, ...) × 256
    data_even = data_no_cs[:, 1::2].astype(np.int64)
    checksums += np.sum(data_even, axis=1) * 256
    
    # Mod by 65536 to handle overflow
    checksums = checksums % 65536
    
    # Compare with stored checksums
    stored_checksums = np.array([int(s['Checksum']) for s in sections])
    bad_mask = checksums != stored_checksums
    
    if np.any(bad_mask):
        print(f"Warning: {np.sum(bad_mask)} sections failed checksum validation")
        sections = [s for i, s in enumerate(sections) if not bad_mask[i]]
    
    return sections


def _read_uint16(data: np.ndarray, endianness: str) -> np.ndarray:
    """Read uint16 values from byte pairs."""
    if endianness == 'little':
        return data[:, 0].astype(np.uint16) + (data[:, 1].astype(np.uint16) << 8)
    else:
        return (data[:, 0].astype(np.uint16) << 8) + data[:, 1].astype(np.uint16)


def _read_int16(data: np.ndarray, endianness: str) -> np.ndarray:
    """Read int16 values from byte pairs."""
    uint_val = _read_uint16(data, endianness)
    return uint_val.astype(np.int16)


def _read_uint32(data: np.ndarray, endianness: str) -> int:
    """Read uint32 value from 4 bytes."""
    if endianness == 'little':
        return int(data[0]) + (int(data[1]) << 8) + (int(data[2]) << 16) + (int(data[3]) << 24)
    else:
        return (int(data[0]) << 24) + (int(data[1]) << 16) + (int(data[2]) << 8) + int(data[3])


def _read_clock_data(data: np.ndarray) -> float:
    """Read clock data and return MATLAB datenum.
    
    Clock data format (6 bytes):
    - Minute (0-59)
    - Second (0-59)
    - Day (1-31)
    - Hour (0-23)
    - Year (0-99, 0=2000)
    - Month (1-12)
    
    Returns MATLAB datenum (days since 0000-01-01).
    """
    from datetime import datetime
    
    # Each byte is BCD-encoded (two decimal digits per byte).
    # Mirrors MATLAB readClockData:
    #   date = 10*bitand(bitshift(data,-4),15) + bitand(data,15)
    def _bcd(b: int) -> int:
        b = int(b)
        return 10 * ((b >> 4) & 0x0F) + (b & 0x0F)
    
    minute = _bcd(data[0])
    second = _bcd(data[1])
    day = _bcd(data[2])
    hour = _bcd(data[3])
    year = _bcd(data[4])
    month = _bcd(data[5])
    
    # Convert 2-digit year to 4-digit (pg 52 of system integrator manual)
    if year >= 90:
        year = year + 1900
    else:
        year = year + 2000
    
    try:
        dt = datetime(year, month, day, hour, minute, second)
        # Convert to MATLAB datenum
        ordinal = dt.toordinal()
        frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
        return ordinal + 366 + frac  # MATLAB epoch offset
    except (ValueError, OverflowError):
        return np.nan


# Section parser functions will be implemented below
# For now, I'll add placeholder implementations for the most critical ones

def _read_user_configuration(data: np.ndarray, endianness: str) -> list[dict]:
    """Read User Configuration section (ID 0x00).
    
    Contains deployment configuration parameters.
    System Integrator Manual pg 30-32.
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse clock data (bytes 48-53)
        clock_deploy = _read_clock_data(record[48:54])
        
        # Parse uint32
        diag_interval = _read_uint32(record[54:58], endianness)
        
        # Parse strings
        deploy_name = record[40:46].tobytes().decode('ascii', errors='ignore').strip()
        comments = record[256:436].tobytes().decode('ascii', errors='ignore').strip()
        
        # Parse uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        t1 = _read_uint16(record[4:6].reshape(1, 2), endianness)[0]
        t2 = _read_uint16(record[6:8].reshape(1, 2), endianness)[0]
        t3 = _read_uint16(record[8:10].reshape(1, 2), endianness)[0]
        t4 = _read_uint16(record[10:12].reshape(1, 2), endianness)[0]
        t5 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        n_pings = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        avg_interval = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        n_beams = _read_uint16(record[18:20].reshape(1, 2), endianness)[0]
        coord_system = _read_uint16(record[32:34].reshape(1, 2), endianness)[0]
        n_bins = _read_uint16(record[34:36].reshape(1, 2), endianness)[0]
        bin_length = _read_uint16(record[36:38].reshape(1, 2), endianness)[0]
        meas_interval = _read_uint16(record[38:40].reshape(1, 2), endianness)[0]
        wrap_mode = _read_uint16(record[46:48].reshape(1, 2), endianness)[0]
        # Mode is the first uint16 of block2 (data(:,59:74) in MATLAB -> bytes 58:60)
        mode = _read_uint16(record[58:60].reshape(1, 2), endianness)[0]
        # TimCtrlReg (timing control register), MATLAB block1 index 10 -> bytes 20:22
        tim_ctrl_reg = _read_uint16(record[20:22].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[510:512].reshape(1, 2), endianness)[0]
        
        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'T1': t1,
            'T2': t2,
            'T3': t3,
            'T4': t4,
            'T5': t5,
            'NPings': n_pings,
            'AvgInterval': avg_interval,
            'NBeams': n_beams,
            'CoordSystem': coord_system,
            'NBins': n_bins,
            'BinLength': bin_length,
            'MeasInterval': meas_interval,
            'DeployName': deploy_name,
            'WrapMode': wrap_mode,
            'Mode': mode,
            'TimCtrlReg': tim_ctrl_reg,
            'clockDeploy': clock_deploy,
            'DiagInterval': diag_interval,
            'Comments': comments,
            'Checksum': checksum,
        }
        
        sections.append(section)
    
    return sections


def _read_head_configuration(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Head Configuration section (ID 0x04).
    
    Contains head/sensor configuration.
    System Integrator Manual pg 29.
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse serial number
        serial_no = record[10:22].tobytes().decode('ascii', errors='ignore').strip()
        
        # Parse transformation matrix (9 int16 values / 4096)
        # MATLAB: reshape(...,3,3) col-major then permute([2 1]) == numpy row-major
        # reshape with NO transpose.
        transform_bytes = record[30:48]
        transform_vals = _read_int16(transform_bytes.reshape(-1, 2), endianness) / 4096.0
        transformation_matrix = transform_vals.reshape(3, 3)
        
        # uint16 fields. Mirrors MATLAB readHeadConfiguration:
        #   block1 = data(3:10), block2 = data(221:224); parsed as 6 uint16:
        #   Size, Config, Frequency, Type, NBeams, Checksum
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        config = _read_uint16(record[4:6].reshape(1, 2), endianness)[0]
        frequency = _read_uint16(record[6:8].reshape(1, 2), endianness)[0]
        head_type = _read_uint16(record[8:10].reshape(1, 2), endianness)[0]
        n_beams = _read_uint16(record[220:222].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[222:224].reshape(1, 2), endianness)[0]
        
        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Config': config,
            'Frequency': frequency,
            'Type': head_type,
            'SerialNo': serial_no,
            'NBeams': n_beams,
            'TransformationMatrix': transformation_matrix,
            'Checksum': checksum,
        }
        
        sections.append(section)
    
    return sections


def _read_hardware_configuration(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Hardware Configuration section (ID 0x05).
    
    Contains hardware/serial number info.
    System Integrator Manual pg 28.
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse serial number (bytes 5-18) and firmware (bytes 43-46)
        # Mirrors MATLAB readHardwareConfiguration: SerialNo=data(5:18),
        # FWversion=data(43:46).
        serial_no = record[4:18].tobytes().decode('ascii', errors='ignore').strip()
        fw_version = record[42:46].tobytes().decode('ascii', errors='ignore').strip()
        
        # Parse uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        config = _read_uint16(record[22:24].reshape(1, 2), endianness)[0]
        frequency = _read_uint16(record[24:26].reshape(1, 2), endianness)[0]
        pic_version = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        hw_revision = _read_uint16(record[28:30].reshape(1, 2), endianness)[0]
        rec_size = _read_uint16(record[30:32].reshape(1, 2), endianness)[0]
        status = _read_uint16(record[32:34].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[46:48].reshape(1, 2), endianness)[0]
        
        # Determine instrument type from serial number
        instrument_type = 'UNKNOWN'
        if 'VNO' in serial_no:
            instrument_type = 'VECTRINO'
        elif 'VEC' in serial_no:
            instrument_type = 'VECTOR'
        elif 'AQD' in serial_no:
            # Check spare bytes for HR flag
            if record[34] == 103 and record[35] == 103:  # 0x67 = 103
                instrument_type = 'HR_PROFILER'
            else:
                instrument_type = 'AQUADOPP_PROFILER'
        elif 'WPR' in serial_no:
            instrument_type = 'AWAC'
        
        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'SerialNo': serial_no,
            'FWversion': fw_version,
            'Config': config,
            'Frequency': frequency,
            'PICversion': pic_version,
            'HWrevision': hw_revision,
            'RecSize': rec_size,
            'Status': status,
            'instrumentType': instrument_type,
            'Checksum': checksum,
        }
        
        sections.append(section)
    
    return sections


def _read_awac_velocity_profile(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Velocity Profile section (ID 0x20).
    
    Contains velocity data for all beams and cells.
    System Integrator Manual pg 46-47.
    """
    n_records = data.shape[0]
    sections = []
    
    # Calculate number of cells from structure size (first record)
    size = _read_uint16(data[0, 2:4].reshape(1, 2), endianness)[0]
    n_cells = int(np.floor(((size * 2) - (118 + 2)) / (3 * 2 + 3)))
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse clock data
        time = _read_clock_data(record[4:10])
        
        # Parse int16 fields
        error = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        heading = _read_int16(record[18:20].reshape(1, 2), endianness)[0]
        pitch = _read_int16(record[20:22].reshape(1, 2), endianness)[0]
        roll = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        temperature = _read_int16(record[28:30].reshape(1, 2), endianness)[0]
        
        # Parse uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        analn1 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        battery = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        analn2 = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        pressure_lsw = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        
        # Parse uint8 fields
        pressure_msb = record[24]
        status = record[25]
        
        # Calculate velocity and amplitude offsets
        vel1_off = 118
        vel2_off = vel1_off + n_cells * 2
        vel3_off = vel2_off + n_cells * 2
        amp1_off = vel3_off + n_cells * 2
        amp2_off = amp1_off + n_cells
        amp3_off = amp2_off + n_cells
        cs_off = amp3_off + n_cells
        
        # Fill value if odd number of cells
        if n_cells % 2:
            cs_off += 1
        
        # Parse velocity data (int16)
        vel1 = _read_int16(record[vel1_off:vel1_off + n_cells * 2].reshape(-1, 2), endianness)
        vel2 = _read_int16(record[vel2_off:vel2_off + n_cells * 2].reshape(-1, 2), endianness)
        vel3 = _read_int16(record[vel3_off:vel3_off + n_cells * 2].reshape(-1, 2), endianness)
        
        # Parse amplitude data (uint8)
        amp1 = record[amp1_off:amp1_off + n_cells]
        amp2 = record[amp2_off:amp2_off + n_cells]
        amp3 = record[amp3_off:amp3_off + n_cells]
        
        # Parse checksum
        checksum = _read_uint16(record[cs_off:cs_off + 2].reshape(1, 2), endianness)[0]
        
        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Time': time,
            'Error': error,
            'Analn1': analn1,
            'Battery': battery,
            'Analn2': analn2,
            'Heading': heading,
            'Pitch': pitch,
            'Roll': roll,
            'PressureMSB': pressure_msb,
            'Status': status,
            'PressureLSW': pressure_lsw,
            'Temperature': temperature,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Checksum': checksum,
        }
        
        sections.append(section)
    
    return sections


def _read_awac_processed_velocity(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Processed Velocity section (ID 0x6A).
    
    Contains tilt-corrected velocity data.
    System Integrator Manual pg 55-56.
    """
    n_records = data.shape[0]
    sections = []
    
    # Get number of cells from first record
    n_cells = data[0, 13]
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse clock data with milliseconds
        time = _read_clock_data(record[4:10])
        milliseconds = _read_uint16(record[10:12].reshape(1, 2), endianness)[0]
        time = time + (milliseconds / 1000 / 60 / 60 / 24)  # Add fractional day
        
        # Parse header
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        beams = record[12]
        cells = record[13]
        
        # Calculate offsets
        vel1_off = 14
        vel2_off = vel1_off + n_cells * 2
        vel3_off = vel2_off + n_cells * 2
        snr1_off = vel3_off + n_cells * 2
        snr2_off = snr1_off + n_cells * 2
        snr3_off = snr2_off + n_cells * 2
        std1_off = snr3_off + n_cells * 2
        std2_off = std1_off + n_cells * 2
        std3_off = std2_off + n_cells * 2
        erc1_off = std3_off + n_cells * 2
        erc2_off = erc1_off + n_cells
        erc3_off = erc2_off + n_cells
        spd_off = erc3_off + n_cells
        dir_off = spd_off + n_cells * 2
        vdt_off = dir_off + n_cells * 2
        perc_off = vdt_off + n_cells * 2
        qc_off = perc_off + n_cells
        cs_off = qc_off + n_cells
        
        # Fill value if odd cells
        if n_cells % 2:
            cs_off += 1
        
        # Parse velocity (int16)
        vel1 = _read_int16(record[vel1_off:vel1_off + n_cells * 2].reshape(-1, 2), endianness)
        vel2 = _read_int16(record[vel2_off:vel2_off + n_cells * 2].reshape(-1, 2), endianness)
        vel3 = _read_int16(record[vel3_off:vel3_off + n_cells * 2].reshape(-1, 2), endianness)
        
        # Parse SNR (uint16)
        snr1 = _read_uint16(record[snr1_off:snr1_off + n_cells * 2].reshape(-1, 2), endianness)
        snr2 = _read_uint16(record[snr2_off:snr2_off + n_cells * 2].reshape(-1, 2), endianness)
        snr3 = _read_uint16(record[snr3_off:snr3_off + n_cells * 2].reshape(-1, 2), endianness)
        
        # Parse standard deviation (uint16)
        std1 = _read_uint16(record[std1_off:std1_off + n_cells * 2].reshape(-1, 2), endianness)
        std2 = _read_uint16(record[std2_off:std2_off + n_cells * 2].reshape(-1, 2), endianness)
        std3 = _read_uint16(record[std3_off:std3_off + n_cells * 2].reshape(-1, 2), endianness)
        
        # Parse error codes (uint8)
        erc1 = record[erc1_off:erc1_off + n_cells]
        erc2 = record[erc2_off:erc2_off + n_cells]
        erc3 = record[erc3_off:erc3_off + n_cells]
        
        # Parse speed and direction (uint16)
        speed = _read_uint16(record[spd_off:spd_off + n_cells * 2].reshape(-1, 2), endianness)
        direction = _read_uint16(record[dir_off:dir_off + n_cells * 2].reshape(-1, 2), endianness)
        vertical_dist = _read_uint16(record[vdt_off:vdt_off + n_cells * 2].reshape(-1, 2), endianness)
        
        # Parse QC flags (uint8)
        profile_error_code = record[perc_off:perc_off + n_cells]
        qc_flag = record[qc_off:qc_off + n_cells]
        
        # Apply QC flag filtering (bad data = NaN)
        speed = speed.astype(np.float32)
        direction = direction.astype(np.float32)
        speed[qc_flag == 1] = np.nan
        direction[qc_flag == 1] = np.nan
        
        # Parse checksum
        checksum = _read_uint16(record[cs_off:cs_off + 2].reshape(1, 2), endianness)[0]
        
        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Time': time,
            'Beams': beams,
            'Cells': cells,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Snr1': snr1,
            'Snr2': snr2,
            'Snr3': snr3,
            'Std1': std1,
            'Std2': std2,
            'Std3': std3,
            'Erc1': erc1,
            'Erc2': erc2,
            'Erc3': erc3,
            'speed': speed,
            'direction': direction,
            'verticalDistance': vertical_dist,
            'profileErrorCode': profile_error_code,
            'qcFlag': qc_flag,
            'Checksum': checksum,
        }
        
        sections.append(section)
    
    return sections


def _read_aquadopp_velocity(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Aquadopp Velocity Data section (ID 0x01).

    Single-cell current meter velocity record.
    Mirrors MATLAB readAquadoppVelocity (System Integrator Manual pg 34-35).
    """
    n_records = data.shape[0]
    sections = []

    for i in range(n_records):
        record = data[i, :]

        # Clock data (bytes 4-9)
        time = _read_clock_data(record[4:10])

        # int16 fields
        error = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        heading = _read_int16(record[18:20].reshape(1, 2), endianness)[0]
        pitch = _read_int16(record[20:22].reshape(1, 2), endianness)[0]
        roll = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        temperature = _read_int16(record[28:30].reshape(1, 2), endianness)[0]
        vel1 = _read_int16(record[30:32].reshape(1, 2), endianness)[0]
        vel2 = _read_int16(record[32:34].reshape(1, 2), endianness)[0]
        vel3 = _read_int16(record[34:36].reshape(1, 2), endianness)[0]

        # uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        analn1 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        battery = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        analn2 = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        pressure_lsw = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[40:42].reshape(1, 2), endianness)[0]

        # uint8 fields
        pressure_msb = record[24]
        status = record[25]
        amp1 = record[36]
        amp2 = record[37]
        amp3 = record[38]
        fill = record[39]

        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Time': time,
            'Error': error,
            'PressureMSB': pressure_msb,
            'Status': status,
            'PressureLSW': pressure_lsw,
            'Checksum': checksum,
            'Analn1': analn1,
            'Battery': battery,
            'Analn2': analn2,
            'Heading': heading,
            'Pitch': pitch,
            'Roll': roll,
            'Temperature': temperature,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Fill': fill,
        }

        sections.append(section)

    return sections

def _read_aquadopp_diag_header(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Aquadopp Diagnostics Data Header section (ID 0x06).

    Mirrors MATLAB readAquadoppDiagHeader (System Integrator Manual pg 35).
    """
    n_records = data.shape[0]
    sections = []

    for i in range(n_records):
        record = data[i, :]

        # uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        records_count = _read_uint16(record[4:6].reshape(1, 2), endianness)[0]
        cell = _read_uint16(record[6:8].reshape(1, 2), endianness)[0]
        proc_magn1 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        proc_magn2 = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        proc_magn3 = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        proc_magn4 = _read_uint16(record[18:20].reshape(1, 2), endianness)[0]
        distance1 = _read_uint16(record[20:22].reshape(1, 2), endianness)[0]
        distance2 = _read_uint16(record[22:24].reshape(1, 2), endianness)[0]
        distance3 = _read_uint16(record[24:26].reshape(1, 2), endianness)[0]
        distance4 = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[34:36].reshape(1, 2), endianness)[0]

        # uint8 noise fields (bytes 8-11)
        noise1 = record[8]
        noise2 = record[9]
        noise3 = record[10]
        noise4 = record[11]

        section = {
            'Sync': record[0],
            'Id': record[1],
            'Checksum': checksum,
            'Size': size,
            'Records': records_count,
            'Cell': cell,
            'ProcMagn1': proc_magn1,
            'ProcMagn2': proc_magn2,
            'ProcMagn3': proc_magn3,
            'ProcMagn4': proc_magn4,
            'Distance1': distance1,
            'Distance2': distance2,
            'Distance3': distance3,
            'Distance4': distance4,
            'Noise1': noise1,
            'Noise2': noise2,
            'Noise3': noise3,
            'Noise4': noise4,
        }

        sections.append(section)

    return sections

def _read_vector_velocity(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_vector_system(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_aquadopp_profiler_velocity(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Aquadopp Profiler Velocity Data section (ID 0x21).

    Multi-cell profile velocity record.
    Mirrors MATLAB readAquadoppProfilerVelocity (System Integrator Manual pg 42-43).
    """
    n_records = data.shape[0]
    sections = []

    # Calculate number of cells from structure size (first record)
    # (* 2 because size is specified in 16-bit words)
    size0 = int(_read_uint16(data[0, 2:4].reshape(1, 2), endianness)[0])
    n_cells = int(np.floor((size0 * 2 - (30 + 2)) / (3 * 2 + 3)))

    # Offsets (0-indexed). MATLAB vel1Off = 31 (1-indexed) -> 30 here.
    vel1_off = 30
    vel2_off = vel1_off + n_cells * 2
    vel3_off = vel2_off + n_cells * 2
    amp1_off = vel3_off + n_cells * 2
    amp2_off = amp1_off + n_cells
    amp3_off = amp2_off + n_cells
    cs_off = amp3_off + n_cells

    # A fill byte is present if the number of cells is odd
    if n_cells % 2:
        cs_off += 1

    for i in range(n_records):
        record = data[i, :]

        # Clock data (bytes 4-9)
        time = _read_clock_data(record[4:10])

        # int16 fields
        error = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        heading = _read_int16(record[18:20].reshape(1, 2), endianness)[0]
        pitch = _read_int16(record[20:22].reshape(1, 2), endianness)[0]
        roll = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        temperature = _read_int16(record[28:30].reshape(1, 2), endianness)[0]

        # uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        analn1 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        battery = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        analn2 = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        pressure_lsw = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        checksum = _read_uint16(record[cs_off:cs_off + 2].reshape(1, 2), endianness)[0]

        # uint8 fields
        pressure_msb = record[24]
        status = record[25]

        # velocity (int16) and amplitude (uint8) arrays
        vel1 = _read_int16(record[vel1_off:vel1_off + n_cells * 2].reshape(-1, 2), endianness)
        vel2 = _read_int16(record[vel2_off:vel2_off + n_cells * 2].reshape(-1, 2), endianness)
        vel3 = _read_int16(record[vel3_off:vel3_off + n_cells * 2].reshape(-1, 2), endianness)
        amp1 = record[amp1_off:amp1_off + n_cells]
        amp2 = record[amp2_off:amp2_off + n_cells]
        amp3 = record[amp3_off:amp3_off + n_cells]

        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Time': time,
            'Error': error,
            'PressureMSB': pressure_msb,
            'Status': status,
            'PressureLSW': pressure_lsw,
            'Temperature': temperature,
            'Checksum': checksum,
            'Analn1': analn1,
            'Battery': battery,
            'Analn2': analn2,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Heading': heading,
            'Pitch': pitch,
            'Roll': roll,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
        }

        sections.append(section)

    return sections

def _read_continental(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Continental Data section (ID 0x24).

    Mirrors MATLAB readContinental: structure is identical to the AWAC
    velocity profile data section (System Integrator Manual pg 50).
    """
    return _read_awac_velocity_profile(data, endianness)

def _read_hr_aquadopp_profile(data: np.ndarray, endianness: str) -> list[dict]:
    """Read High Resolution Aquadopp Profile Data section (ID 0x2A).

    Mirrors MATLAB readHRAquadoppProfile (System Integrator Manual pg 43-45).
    """
    n_records = data.shape[0]
    sections = []

    n_beams = int(data[0, 34])
    n_cells = int(data[0, 35])

    # Per-record data offsets (0-indexed). MATLAB velOff = 55 (1-indexed).
    vel_off = 54
    amp_off = vel_off + n_beams * n_cells * 2
    corr_off = amp_off + n_beams * n_cells
    cs_off = corr_off + n_beams * n_cells

    for i in range(n_records):
        record = data[i, :]

        time = _read_clock_data(record[4:10])

        # int16 fields
        milliseconds = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        error = _read_int16(record[12:14].reshape(1, 2), endianness)[0]
        heading = _read_int16(record[18:20].reshape(1, 2), endianness)[0]
        pitch = _read_int16(record[20:22].reshape(1, 2), endianness)[0]
        roll = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        temperature = _read_int16(record[28:30].reshape(1, 2), endianness)[0]

        # uint16 fields
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        battery = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        speed_of_sound = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        pressure_lsw = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        analn1 = _read_uint16(record[30:32].reshape(1, 2), endianness)[0]
        analn2 = _read_uint16(record[32:34].reshape(1, 2), endianness)[0]
        vel_lag2 = _read_uint16(record[36:42].reshape(-1, 2), endianness)
        checksum = _read_uint16(record[cs_off:cs_off + 2].reshape(1, 2), endianness)[0]

        # uint8 fields
        pressure_msb = record[24]
        status = record[25]
        beams = record[34]
        cells = record[35]
        amp_lag2 = record[42:45]
        corr_lag2 = record[45:48]

        # Per-beam velocity/amplitude/correlation arrays
        vel = []
        amp = []
        cor = []
        for k in range(n_beams):
            s_vel = vel_off + k * n_cells * 2
            vel.append(_read_int16(record[s_vel:s_vel + n_cells * 2].reshape(-1, 2), endianness))
            s_amp = amp_off + k * n_cells
            amp.append(record[s_amp:s_amp + n_cells])
            s_cor = corr_off + k * n_cells
            cor.append(record[s_cor:s_cor + n_cells])

        section = {
            'Sync': record[0],
            'Id': record[1],
            'Size': size,
            'Time': time,
            'PressureMSB': pressure_msb,
            'Status': status,
            'PressureLSW': pressure_lsw,
            'Temperature': temperature,
            'Beams': beams,
            'Cells': cells,
            'VelLag2': vel_lag2,
            'Battery': battery,
            'SpeedOfSound': speed_of_sound,
            'Analn1': analn1,
            'Analn2': analn2,
            'Milliseconds': milliseconds,
            'Error': error,
            'Heading': heading,
            'Pitch': pitch,
            'Roll': roll,
            'AmpLag2': amp_lag2,
            'CorrLag2': corr_lag2,
            'Checksum': checksum,
            'Vel1': vel[0] if n_beams > 0 else np.array([]),
            'Amp1': amp[0] if n_beams > 0 else np.array([]),
            'Corr1': cor[0] if n_beams > 0 else np.array([]),
            'Vel2': vel[1] if n_beams > 1 else np.array([]),
            'Amp2': amp[1] if n_beams > 1 else np.array([]),
            'Corr2': cor[1] if n_beams > 1 else np.array([]),
            'Vel3': vel[2] if n_beams > 2 else np.array([]),
            'Amp3': amp[2] if n_beams > 2 else np.array([]),
            'Corr3': cor[2] if n_beams > 2 else np.array([]),
        }

        sections.append(section)

    return sections

def _read_awac_wave_data(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Wave Data section (ID 0x30).
    
    Mirrors MATLAB readAwacWaveData (System Integrator Manual pg 49).
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        # Parse uint16 block (bytes 5-10): Pressure, Distance, Analn
        pressure = _read_uint16(record[4:6].reshape(1, 2), endianness)[0]
        distance = _read_uint16(record[6:8].reshape(1, 2), endianness)[0]
        analn = _read_uint16(record[8:10].reshape(1, 2), endianness)[0]
        
        # Parse int16 block (bytes 11-18): Vel1-4
        vel1 = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        vel2 = _read_int16(record[12:14].reshape(1, 2), endianness)[0]
        vel3 = _read_int16(record[14:16].reshape(1, 2), endianness)[0]
        vel4 = _read_int16(record[16:18].reshape(1, 2), endianness)[0]
        
        # Parse uint8 block (bytes 19-22): Amp1-3, Amp4ASTQual
        amp1 = int(record[18])
        amp2 = int(record[19])
        amp3 = int(record[20])
        amp4_ast_qual = int(record[21])
        
        # Checksum (bytes 23-24)
        checksum = _read_uint16(record[22:24].reshape(1, 2), endianness)[0]
        
        sections.append({
            'Sync': int(record[0]),
            'Id': int(record[1]),
            'Size': _read_uint16(record[2:4].reshape(1, 2), endianness)[0],
            'Pressure': pressure,
            'Distance': distance,
            'Analn': analn,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Vel4': vel4,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Amp4ASTQual': amp4_ast_qual,
            'Checksum': checksum,
        })
    
    return sections

def _read_awac_wave_header(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Wave Data Header section (ID 0x31).
    
    Mirrors MATLAB readAwacWaveHeader (System Integrator Manual pg 49).
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        time = _read_clock_data(record[4:10])
        
        # uint16 block (bytes 11-18): NRecords, Blanking, Battery, SoundSpeed
        n_wave_records = _read_uint16(record[10:12].reshape(1, 2), endianness)[0]
        blanking = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        battery = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        sound_speed = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        
        # int16 block (bytes 19-24): Heading, Pitch, Roll
        heading = _read_int16(record[18:20].reshape(1, 2), endianness)[0]
        pitch = _read_int16(record[20:22].reshape(1, 2), endianness)[0]
        roll = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        
        # uint16 block (bytes 25-28): MinPress, HMaxPress
        min_press = _read_uint16(record[24:26].reshape(1, 2), endianness)[0]
        h_max_press = _read_uint16(record[26:28].reshape(1, 2), endianness)[0]
        
        # int16 (bytes 29-30): Temperature
        temperature = _read_int16(record[28:30].reshape(1, 2), endianness)[0]
        
        # uint16 (bytes 31-32): CellSize
        cell_size = _read_uint16(record[30:32].reshape(1, 2), endianness)[0]
        
        # uint8 (bytes 33-36): Noise1-4
        noise1 = int(record[32])
        noise2 = int(record[33])
        noise3 = int(record[34])
        noise4 = int(record[35])
        
        # uint16 (bytes 37-44): ProcMagn1-4
        proc_magn1 = _read_uint16(record[36:38].reshape(1, 2), endianness)[0]
        proc_magn2 = _read_uint16(record[38:40].reshape(1, 2), endianness)[0]
        proc_magn3 = _read_uint16(record[40:42].reshape(1, 2), endianness)[0]
        proc_magn4 = _read_uint16(record[42:44].reshape(1, 2), endianness)[0]
        
        # Checksum (bytes 59-60, bytes 44-58 are spare)
        checksum = _read_uint16(record[58:60].reshape(1, 2), endianness)[0]
        
        sections.append({
            'Sync': int(record[0]),
            'Id': int(record[1]),
            'Size': _read_uint16(record[2:4].reshape(1, 2), endianness)[0],
            'Time': time,
            'NRecords': n_wave_records,
            'Blanking': blanking,
            'Battery': battery,
            'SoundSpeed': sound_speed,
            'Heading': heading,
            'Pitch': pitch,
            'Roll': roll,
            'MinPress': min_press,
            'HMaxPress': h_max_press,
            'Temperature': temperature,
            'CellSize': cell_size,
            'Noise1': noise1,
            'Noise2': noise2,
            'Noise3': noise3,
            'Noise4': noise4,
            'ProcMagn1': proc_magn1,
            'ProcMagn2': proc_magn2,
            'ProcMagn3': proc_magn3,
            'ProcMagn4': proc_magn4,
            'Checksum': checksum,
        })
    
    return sections

def _read_awac_wave_data_suv(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Wave Data SUV section (ID 0x36).
    
    Mirrors MATLAB readAwacWaveDataSUV (System Integrator Manual pg 49-50).
    """
    n_records = data.shape[0]
    sections = []
    
    for i in range(n_records):
        record = data[i, :]
        
        # uint16 block (bytes 3-8): Heading, Pressure, Distance
        heading = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        pressure = _read_uint16(record[4:6].reshape(1, 2), endianness)[0]
        distance = _read_uint16(record[6:8].reshape(1, 2), endianness)[0]
        
        # uint8 (bytes 9-10): Pitch, Roll
        pitch = int(record[8])
        roll = int(record[9])
        
        # int16 block (bytes 11-18): Vel1-4
        vel1 = _read_int16(record[10:12].reshape(1, 2), endianness)[0]
        vel2 = _read_int16(record[12:14].reshape(1, 2), endianness)[0]
        vel3 = _read_int16(record[14:16].reshape(1, 2), endianness)[0]
        vel4_distance2 = _read_int16(record[16:18].reshape(1, 2), endianness)[0]
        
        # uint8 block (bytes 19-22): Amp1-3, Amp4ASTQual
        amp1 = int(record[18])
        amp2 = int(record[19])
        amp3 = int(record[20])
        amp4_ast_qual = int(record[21])
        
        # Checksum (bytes 23-24)
        checksum = _read_uint16(record[22:24].reshape(1, 2), endianness)[0]
        
        sections.append({
            'Sync': int(record[0]),
            'Id': int(record[1]),
            'Heading': heading,
            'Pressure': pressure,
            'Distance': distance,
            'Pitch': pitch,
            'Roll': roll,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Vel4Distance2': vel4_distance2,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Amp4ASTQual': amp4_ast_qual,
            'Checksum': checksum,
        })
    
    return sections

def _read_awac_stage_data(data: np.ndarray, endianness: str) -> list[dict]:
    """Read AWAC Stage Data section (ID 0x42).
    
    Mirrors MATLAB readAwacStageData (System Integrator Manual pg 48).
    Variable size section — AST window cells.
    """
    n_records = data.shape[0]
    sections = []
    
    # Calculate nCells from size field of first record
    size_val = int(_read_uint16(data[0, 2:4].reshape(1, 2), endianness)[0])
    n_cells = int(np.floor((size_val * 2) - (32 + 2)))
    
    for i in range(n_records):
        record = data[i, :]
        
        size = _read_uint16(record[2:4].reshape(1, 2), endianness)[0]
        
        # uint8 (bytes 7-9): Amp1, Amp2, Amp3
        amp1 = int(record[6])
        amp2 = int(record[7])
        amp3 = int(record[8])
        
        # uint16 block (bytes 11-20): Pressure, AST1, ASTquality, SoundSpeed, AST2
        pressure = _read_uint16(record[10:12].reshape(1, 2), endianness)[0]
        ast1 = _read_uint16(record[12:14].reshape(1, 2), endianness)[0]
        ast_quality = _read_uint16(record[14:16].reshape(1, 2), endianness)[0]
        sound_speed = _read_uint16(record[16:18].reshape(1, 2), endianness)[0]
        ast2 = _read_uint16(record[18:20].reshape(1, 2), endianness)[0]
        
        # int16 block (bytes 23-28): Vel1, Vel2, Vel3
        vel1 = _read_int16(record[22:24].reshape(1, 2), endianness)[0]
        vel2 = _read_int16(record[24:26].reshape(1, 2), endianness)[0]
        vel3 = _read_int16(record[26:28].reshape(1, 2), endianness)[0]
        
        # Amplitude profile (variable length, starts at byte 33)
        amp_off = 32
        cs_off = amp_off + n_cells
        if n_cells % 2:
            cs_off += 1
        
        amp = record[amp_off:amp_off + n_cells].copy()
        
        checksum = _read_uint16(record[cs_off:cs_off + 2].reshape(1, 2), endianness)[0]
        
        sections.append({
            'Sync': int(record[0]),
            'Id': int(record[1]),
            'Size': size,
            'Amp1': amp1,
            'Amp2': amp2,
            'Amp3': amp3,
            'Pressure': pressure,
            'AST1': ast1,
            'ASTquality': ast_quality,
            'SoundSpeed': sound_speed,
            'AST2': ast2,
            'Vel1': vel1,
            'Vel2': vel2,
            'Vel3': vel3,
            'Amp': amp,
            'Checksum': checksum,
        })
    
    return sections

def _read_vectrino_velocity_header(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_vectrino_velocity(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_wave_parameter_estimates(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_wave_band_estimates(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_wave_energy_spectrum(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_wave_fourier_coefficient_spectrum(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_awac_ast(data: np.ndarray, endianness: str) -> list[dict]:
    return []

def _read_aquadopp_diagnostics(data: np.ndarray, endianness: str) -> list[dict]:
    """Read Aquadopp Diagnostics Data section (ID 0x80).

    Mirrors MATLAB readAquadoppDiagnostics: same structure as the Aquadopp
    velocity section (System Integrator Manual pg 36).
    """
    return _read_aquadopp_velocity(data, endianness)

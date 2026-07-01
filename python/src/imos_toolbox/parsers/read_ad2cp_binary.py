"""AD2CP binary format reader for Nortek Signature instruments.

Port of MATLAB readAD2CPBinary.m.
Reads raw binary .ad2cp files from Nortek Signature-series ADCPs.

Binary format: sequential sections, each with:
- Header (10 bytes): sync(0xA5), headerSize, Id, family, dataSize(2), dataChecksum(2), headerChecksum(2)
- Data record: varies by Id and Version

Supported record types:
- 0x15: Burst Data Record (Version 3)
- 0x16: Average Data Record (Version 3)
- 0x17: Bottom Track Data Record
- 0x18: Interleaved Burst (beam 5)
- 0x1A: Burst Altimeter Raw
- 0x1E: Altimeter Record
- 0x1F: Avg Altimeter Raw
- 0xA0: String Data Record

Author: Kiro AI Assistant
Based on MATLAB implementation by Guillaume Galibert
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

SYNC_BYTE = 0xA5
CHECKSUM_INIT = 0xB58C  # Same as Paradopp


def read_ad2cp_binary(filename: Path) -> dict[str, Any]:
    """Read all sections from a Nortek AD2CP binary file.
    
    Mirrors MATLAB readAD2CPBinary.m.
    
    Args:
        filename: Path to .ad2cp binary file
        
    Returns:
        Dictionary keyed by 'Id{hex}_Version{v}_Size{s}' containing
        lists of parsed section data.
    """
    data = np.fromfile(filename, dtype=np.uint8)
    data_len = len(data)
    
    if data_len == 0:
        raise ValueError(f"File {filename} is empty")
    
    structures: dict[str, Any] = {}
    idx = 0
    
    while idx < data_len:
        sect, length = _read_section(data, idx, data_len)
        
        if sect is not None and length > 0:
            # Group by Id, Version, and DataSize (mirrors MATLAB logic)
            header = sect["Header"]
            sect_data = sect.get("Data", {})
            version = sect_data.get("Version")
            
            if version is not None:
                field_name = f"Id{header['Id']}_Version{version}_Size{header['DataSize']}"
            else:
                field_name = f"Id{header['Id']}_Size{header['DataSize']}"
            
            if field_name not in structures:
                structures[field_name] = {"Header": [], "Data": []}
            
            structures[field_name]["Header"].append(header)
            structures[field_name]["Data"].append(sect_data)
            
            idx += length
        elif length and length > 0:
            idx += length
        else:
            idx += 1  # Skip bad byte
    
    return structures


def _read_section(data: np.ndarray, idx: int, data_len: int) -> tuple[dict | None, int]:
    """Read one section from the binary data.
    
    Returns (section_dict, total_length) or (None, skip_length).
    """
    if idx >= data_len:
        return None, 0
    
    # Check sync byte
    if data[idx] != SYNC_BYTE:
        return None, 1
    
    # Need at least 10 bytes for header
    if idx + 10 > data_len:
        return None, 0
    
    header_size = int(data[idx + 1])
    id_byte = int(data[idx + 2])
    id_hex = f"{id_byte:02X}"
    data_size = int(data[idx + 4]) + (int(data[idx + 5]) << 8)
    
    total_len = header_size + data_size
    
    # Check bounds
    if idx + total_len > data_len:
        return None, 0
    
    # Parse header
    header = {
        "Sync": "A5",
        "HeaderSize": header_size,
        "Id": id_hex,
        "Family": f"{int(data[idx + 3]):02X}",
        "DataSize": data_size,
        "DataChecksum": int(data[idx + 6]) + (int(data[idx + 7]) << 8),
        "HeaderChecksum": int(data[idx + 8]) + (int(data[idx + 9]) << 8),
    }
    
    # Verify header checksum
    header_cs = _gen_checksum(data, idx, header_size - 2)
    if header_cs != header["HeaderChecksum"]:
        return None, total_len
    
    # Parse data section based on ID
    data_start = idx + header_size
    sect_data = None
    
    if id_hex in ("15", "16", "18", "1A", "1E", "1F"):
        # Burst/Average/Altimeter data record
        sect_data = _read_burst_average(data, data_start, data_size)
    elif id_hex == "17" or id_hex == "1B":
        # Bottom Track record
        sect_data = _read_bottom_track(data, data_start, data_size)
    elif id_hex == "A0":
        # String data record
        sect_data = _read_string(data, data_start, data_size)
    else:
        # Unsupported — skip
        return None, total_len
    
    if sect_data is None:
        return None, total_len
    
    # Verify data checksum
    data_cs = _gen_checksum(data, data_start, data_size)
    if data_cs != header["DataChecksum"]:
        pass  # Warn but don't discard
    
    return {"Header": header, "Data": sect_data}, total_len


def _read_burst_average(data: np.ndarray, idx: int, size: int) -> dict | None:
    """Read Burst/Average/Altimeter data record.
    
    Dispatches to version-specific reader. Only Version 3 is fully supported
    (matching MATLAB limitation).
    """
    if size < 2:
        return None
    
    version = int(data[idx])
    
    if version == 3:
        return _read_burst_average_v3(data, idx)
    elif version == 2:
        return _read_burst_average_v2(data, idx)
    elif version == 1:
        return _read_burst_average_v1(data, idx)
    else:
        return {"Version": version}


def _read_burst_average_v3(data: np.ndarray, idx: int) -> dict:
    """Read Version 3 Burst/Average data record.
    
    Mirrors MATLAB readBurstAverageVersion3.
    """
    sect: dict[str, Any] = {}
    
    sect["Version"] = int(data[idx])
    sect["OffsetOfData"] = int(data[idx + 1])
    
    # Configuration (16 bits)
    config = int(data[idx + 2]) + (int(data[idx + 3]) << 8)
    is_velocity = bool(config & (1 << 5))
    is_amplitude = bool(config & (1 << 6))
    is_correlation = bool(config & (1 << 7))
    is_altimeter = bool(config & (1 << 8))

    sect["Configuration"] = config
    sect["SerialNumber"] = _read_u32(data, idx + 4)
    sect["Time"] = _read_clock_data(data, idx + 8)
    sect["SpeedOfSound"] = _read_u16(data, idx + 16)
    sect["Temperature"] = _read_i16(data, idx + 18)
    sect["Pressure"] = _read_u32(data, idx + 20)
    sect["Heading"] = _read_u16(data, idx + 24)
    sect["Pitch"] = _read_i16(data, idx + 26)
    sect["Roll"] = _read_i16(data, idx + 28)
    
    # Beams/CoordSys/Cells packed in uint16 at offset 30
    bcc = _read_u16(data, idx + 30)
    sect["nCells"] = bcc & 0x03FF  # bits 0-9
    sect["coordSys"] = (bcc >> 10) & 0x03  # bits 10-11
    sect["nBeams"] = (bcc >> 12) & 0x0F  # bits 12-15
    
    sect["CellSize"] = _read_u16(data, idx + 32)
    sect["Blanking"] = _read_u16(data, idx + 34)
    sect["NominalCorrelation"] = int(data[idx + 36])
    sect["BatteryVoltage"] = _read_u16(data, idx + 38)
    sect["MagRawX"] = _read_i16(data, idx + 40)
    sect["MagRawY"] = _read_i16(data, idx + 42)
    sect["MagRawZ"] = _read_i16(data, idx + 44)
    sect["AccRawX"] = _read_i16(data, idx + 46)
    sect["AccRawY"] = _read_i16(data, idx + 48)
    sect["AccRawZ"] = _read_i16(data, idx + 50)
    sect["AmbiguityVel"] = _read_u16(data, idx + 52)
    sect["TransmitEnergy"] = _read_u16(data, idx + 56)
    sect["VelocityScaling"] = _read_i8(data, idx + 58)
    sect["PowerLevel"] = _read_i8(data, idx + 59)
    sect["Error"] = _read_u32(data, idx + 64)
    sect["Status"] = _read_u32(data, idx + 68)
    sect["EnsembleCounter"] = _read_u32(data, idx + 72)
    
    # Variable-length data after OffsetOfData
    n_cells = sect["nCells"]
    n_beams = sect["nBeams"]
    off = sect["OffsetOfData"] - 1
    
    if is_velocity and n_cells > 0 and n_beams > 0:
        n_vel = n_beams * n_cells * 2
        vel_start = idx + off + 1
        if vel_start + n_vel <= len(data):
            vel_raw = np.frombuffer(data[vel_start:vel_start + n_vel].tobytes(), dtype="<i2")
            sect["VelocityData"] = vel_raw.reshape(n_cells, n_beams).T.copy()
            off += n_vel
    
    if is_amplitude and n_cells > 0 and n_beams > 0:
        n_amp = n_beams * n_cells
        amp_start = idx + off + 1
        if amp_start + n_amp <= len(data):
            amp_raw = data[amp_start:amp_start + n_amp].copy()
            sect["AmplitudeData"] = amp_raw.reshape(n_cells, n_beams).T.copy()
            off += n_amp
    
    if is_correlation and n_cells > 0 and n_beams > 0:
        n_cor = n_beams * n_cells
        cor_start = idx + off + 1
        if cor_start + n_cor <= len(data):
            cor_raw = data[cor_start:cor_start + n_cor].copy()
            sect["CorrelationData"] = cor_raw.reshape(n_cells, n_beams).T.copy()
            off += n_cor
    
    if is_altimeter:
        alt_start = idx + off + 1
        if alt_start + 8 <= len(data):
            sect["AltimeterDistance"] = np.frombuffer(
                data[alt_start:alt_start + 4].tobytes(), dtype="<f4"
            )[0]
            sect["AltimeterQuality"] = _read_u16(data, alt_start + 4)
            off += 8
    
    return sect


def _read_burst_average_v2(data: np.ndarray, idx: int) -> dict:
    """Read Version 2 Burst/Average (simplified — extract key fields)."""
    sect: dict[str, Any] = {}
    sect["Version"] = int(data[idx])
    sect["OffsetOfData"] = int(data[idx + 1])
    sect["SerialNumber"] = _read_u32(data, idx + 2)
    config = _read_u16(data, idx + 6)
    sect["Configuration"] = config
    sect["Time"] = _read_clock_data(data, idx + 8)
    sect["SpeedOfSound"] = _read_u16(data, idx + 16)
    sect["Temperature"] = _read_i16(data, idx + 18)
    sect["Pressure"] = _read_u32(data, idx + 20)
    sect["Heading"] = _read_u16(data, idx + 24)
    sect["Pitch"] = _read_i16(data, idx + 26)
    sect["Roll"] = _read_i16(data, idx + 28)
    sect["Error"] = _read_u16(data, idx + 30)
    sect["Status"] = _read_u16(data, idx + 32)
    bcc = _read_u16(data, idx + 34)
    sect["nCells"] = bcc & 0x03FF
    sect["coordSys"] = (bcc >> 10) & 0x03
    sect["nBeams"] = (bcc >> 12) & 0x0F
    sect["CellSize"] = _read_u16(data, idx + 36)
    sect["Blanking"] = _read_u16(data, idx + 38)
    sect["BatteryVoltage"] = _read_u16(data, idx + 42)
    sect["VelocityScaling"] = _read_i8(data, idx + 62)
    return sect


def _read_burst_average_v1(data: np.ndarray, idx: int) -> dict:
    """Read Version 1 Burst/Average (simplified)."""
    sect: dict[str, Any] = {}
    sect["Version"] = int(data[idx])
    config = int(data[idx + 1])
    sect["Configuration"] = config
    sect["Time"] = _read_clock_data(data, idx + 2)
    sect["SpeedOfSound"] = _read_u16(data, idx + 10)
    sect["Temperature"] = _read_i16(data, idx + 12)
    sect["Pressure"] = _read_u32(data, idx + 14)
    sect["Heading"] = _read_u16(data, idx + 18)
    sect["Pitch"] = _read_i16(data, idx + 20)
    sect["Roll"] = _read_i16(data, idx + 22)
    sect["Error"] = _read_u16(data, idx + 24)
    sect["Status"] = _read_u16(data, idx + 26)
    bcc = _read_u16(data, idx + 28)
    sect["nCells"] = bcc & 0x03FF
    sect["coordSys"] = (bcc >> 10) & 0x03
    sect["nBeams"] = (bcc >> 12) & 0x0F
    sect["CellSize"] = _read_u16(data, idx + 30)
    sect["Blanking"] = _read_u16(data, idx + 32)
    sect["BatteryVoltage"] = _read_u16(data, idx + 37)
    sect["VelocityScaling"] = _read_i8(data, idx + 36)
    return sect


def _read_bottom_track(data: np.ndarray, idx: int, size: int) -> dict:
    """Read Bottom Track record (simplified)."""
    sect: dict[str, Any] = {}
    sect["Version"] = int(data[idx])
    sect["OffsetOfData"] = int(data[idx + 1])
    sect["SerialNumber"] = _read_u32(data, idx + 4)
    sect["Time"] = _read_clock_data(data, idx + 8)
    sect["SpeedOfSound"] = _read_u16(data, idx + 16)
    sect["Temperature"] = _read_i16(data, idx + 18)
    sect["Pressure"] = _read_u32(data, idx + 20)
    sect["Heading"] = _read_u16(data, idx + 24)
    sect["Pitch"] = _read_i16(data, idx + 26)
    sect["Roll"] = _read_i16(data, idx + 28)
    bcc = _read_u16(data, idx + 30)
    sect["nBeams"] = (bcc >> 12) & 0x0F
    sect["BatteryVoltage"] = _read_u16(data, idx + 38)
    return sect


def _read_string(data: np.ndarray, idx: int, size: int) -> dict:
    """Read String data record (GPS NMEA, comments, header info)."""
    sect: dict[str, Any] = {}
    sect["Id"] = int(data[idx])
    sect["String"] = bytes(data[idx + 1:idx + size]).decode("ascii", errors="ignore")
    return sect


def _read_clock_data(data: np.ndarray, idx: int) -> float:
    """Read 8-byte clock data and return MATLAB datenum.
    
    Format: year(+1900), month(+1), day, hour, minute, second, microsecond_hundreds(uint16)
    """
    year = int(data[idx]) + 1900
    month = int(data[idx + 1]) + 1  # Jan=0
    day = int(data[idx + 2])
    hour = int(data[idx + 3])
    minute = int(data[idx + 4])
    second = int(data[idx + 5])
    hundreds_usec = int(data[idx + 6]) + (int(data[idx + 7]) << 8)
    
    fractional_seconds = hundreds_usec / 10000.0
    
    try:
        microseconds = int(fractional_seconds * 1_000_000)
        dt = datetime(year, month, day, hour, minute, second, min(microseconds, 999999))
        ordinal = dt.toordinal()
        frac = (dt - datetime(dt.year, dt.month, dt.day)).total_seconds() / 86400.0
        return ordinal + 366 + frac
    except (ValueError, OverflowError):
        return float("nan")


def _gen_checksum(data: np.ndarray, idx: int, length: int) -> int:
    """Generate checksum (same algorithm as Paradopp/Workhorse).
    
    Start value 0xB58C, sum odd bytes + even bytes×256, mod 65536.
    """
    section = data[idx:idx + length]
    cs = CHECKSUM_INIT
    odd_bytes = section[0::2].astype(np.int64)
    even_bytes = section[1::2].astype(np.int64)
    cs += int(np.sum(odd_bytes)) + int(np.sum(even_bytes)) * 256
    return cs % 65536


# Helper functions for reading binary values
def _read_u16(data: np.ndarray, idx: int) -> int:
    return int(data[idx]) + (int(data[idx + 1]) << 8)

def _read_i16(data: np.ndarray, idx: int) -> int:
    val = int(data[idx]) + (int(data[idx + 1]) << 8)
    return val - 0x10000 if val >= 0x8000 else val

def _read_u32(data: np.ndarray, idx: int) -> int:
    return (int(data[idx]) + (int(data[idx + 1]) << 8) +
            (int(data[idx + 2]) << 16) + (int(data[idx + 3]) << 24))

def _read_i8(data: np.ndarray, idx: int) -> int:
    val = int(data[idx])
    return val - 256 if val >= 128 else val

"""Aquatec AQUAlogger parser.

Exact port of MATLAB aquatecParse.m.
Parses raw data files from Aquatec AQUAlogger 520 series instruments:
  - 520T:  temperature only
  - 520P:  pressure only
  - 520PT: pressure and temperature

File format: key-value pairs separated by commas. Data lines start with
either 'DATA,' or 'BURSTSTART,'. Both are treated identically as data rows.

If burst mode is used and data is not pre-averaged, burst samples are
averaged (mean of each burst's time, temperature, and pressure).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser


class AquatecParser(BaseParser):
    """Parser for Aquatec AQUAlogger exports.

    Mirrors MATLAB aquatecParse.m exactly.
    """

    parser_name = "aquatec"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("aquatec parser currently expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() not in {".txt", ".dat", ".csv"}:
            raise ValueError("aquatec parser currently supports .txt/.dat/.csv files")

        # --- Read file: separate header (key-value) from data ---
        # Mirrors MATLAB: read lines until DATA or BURSTSTART, rest is data.
        lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()

        keys: list[str] = []
        values: list[str] = []
        data_start_idx = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.upper().startswith("DATA") or stripped.upper().startswith("BURSTSTART"):
                data_start_idx = i
                break
            # Parse key,value
            parts = stripped.split(",", 1)
            keys.append(parts[0].strip())
            values.append(parts[1].strip() if len(parts) > 1 else "")
        else:
            raise ValueError(f"No DATA or BURSTSTART lines found in {source_file}")

        # --- Extract metadata from header key-value pairs ---
        def get_value(search_key: str) -> str:
            """Get value for a header key (case-insensitive)."""
            for k, v in zip(keys, values):
                if k.upper() == search_key.upper():
                    return v
            return ""

        # Instrument metadata (mirrors MATLAB getValues calls)
        model_raw = get_value("LOGGER TYPE")
        model = model_raw.replace("Pressure & Temperature", "").replace("Pressure", "").replace("Temperature", "").strip()

        firmware = get_value("VERSION")
        logger_field = get_value("LOGGER")
        serial = logger_field.split(",")[0].strip() if logger_field else ""

        # Regime (mode, interval, samples per burst)
        regime_raw = get_value("REGIME")
        regime_parts = [p.strip() for p in regime_raw.split(",") if p.strip()]

        # Start/stop times for continuous mode fallback
        start_time_str = get_value("START TIME")
        stop_time_str = get_value("STOP TIME")
        start_time = _parse_aquatec_datetime(start_time_str) if start_time_str else None
        stop_time = _parse_aquatec_datetime(stop_time_str) if stop_time_str else None

        # Sample interval from regime (mirrors MATLAB)
        sample_interval_days = 0.0
        if len(regime_parts) >= 2:
            interval_match = re.search(r"([\d.]+)\s*(minute|second)", regime_parts[1], re.IGNORECASE)
            if interval_match:
                amount = float(interval_match.group(1))
                unit = interval_match.group(2).lower()
                if "minute" in unit:
                    sample_interval_days = amount / (24 * 60)
                else:
                    sample_interval_days = amount / (24 * 3600)

        # Burst mode detection (mirrors MATLAB)
        is_burst = len(regime_parts) >= 1 and regime_parts[0].strip().lower() == "burst mode"
        samples_per_burst = 1
        if is_burst and len(regime_parts) >= 3:
            try:
                samples_per_burst = int(regime_parts[2])
            except ValueError:
                samples_per_burst = 1

        # Averaged flag (mirrors MATLAB)
        averaged_raw = get_value("AVERAGED")
        is_averaged = averaged_raw.strip().lower() == "yes"

        # --- Parse HEADING to determine column layout ---
        heading_raw = get_value("HEADING")
        heading = [h.strip() for h in heading_raw.split(",") if h.strip()]

        time_idx = _find_heading_index(heading, "Timecode")
        temp_idx = _find_heading_index(heading, "Ext temperature")
        pres_idx = _find_heading_index(heading, "Pressure")

        # --- Parse data lines ---
        # MATLAB uses textscan with format that skips the DATA/BURSTSTART prefix,
        # then reads 6 time fields (H:M:S D/M/Y split on ': /') and value columns.
        # We replicate this: for each data line, skip prefix, split on ', : /',
        # extract time components and engineering value columns.

        data_block = "\n".join(lines[data_start_idx:])
        time_values: list[float] = []
        temp_values: list[float] = []
        pres_values: list[float] = []

        for line in lines[data_start_idx:]:
            stripped = line.strip()
            if not stripped:
                continue

            # Skip the prefix (DATA or BURSTSTART) — everything after first comma
            _, _, remainder = stripped.partition(",")
            if not remainder:
                continue

            # Split remainder on delimiters: comma, colon, space, slash
            # Mirrors MATLAB: format '%*s' then '%f%f%f%f%f%f' with Delimiter ',: /'
            tokens = re.split(r"[,: /]+", remainder.strip())
            if len(tokens) < 6:
                continue

            # Time: H, M, S, D, M, Y (mirrors MATLAB textscan order with HH:MM:SS DD/MM/YYYY)
            try:
                hour = int(tokens[0])
                minute = int(tokens[1])
                second = int(tokens[2])
                day = int(tokens[3])
                month = int(tokens[4])
                year = int(tokens[5])

                # Handle 2-digit year
                if year < 100:
                    year += 2000

                dt = datetime(year, month, day, hour, minute, second)
                time_val = _datetime_to_matlab_datenum(dt)
            except (ValueError, IndexError):
                continue

            # Skip bad timestamps (mirrors MATLAB: day==0 || month==0 || year==0)
            if day == 0 or month == 0 or year == 0:
                continue

            time_values.append(time_val)

            # Value columns come after the 6 time fields.
            # MATLAB format skips raw counts and reads engineering values:
            # For PT: tokens are [H,M,S,D,M,Y, raw_temp, eng_temp, raw_pres, eng_pres, ...]
            # temp_idx+1 in heading → engineering temp is at value position (temp_idx)
            # pres_idx+1 in heading → engineering pres is at value position (pres_idx)
            value_tokens = tokens[6:]  # Everything after the 6 time parts

            temp_val = np.nan
            pres_val = np.nan

            # Temperature: column after 'Ext temperature' heading
            # In the data, the eng value is at odd positions (1, 3, 5...)
            # MATLAB reads format: for each heading column pair (raw, eng), it reads eng
            if temp_idx is not None and len(value_tokens) > 1:
                try:
                    temp_val = float(value_tokens[1])  # Engineering temp (2nd value)
                except (ValueError, IndexError):
                    temp_val = np.nan

            # Pressure: next pair after temperature
            if pres_idx is not None:
                pres_offset = 2 if temp_idx is not None else 0
                if len(value_tokens) > pres_offset + 1:
                    try:
                        pres_val = float(value_tokens[pres_offset + 1])  # Engineering pres
                    except (ValueError, IndexError):
                        pres_val = np.nan

            temp_values.append(temp_val)
            pres_values.append(pres_val)

        if not time_values:
            # Fallback: generate timestamps from start/stop/interval
            if start_time and stop_time and sample_interval_days > 0:
                start_dn = _datetime_to_matlab_datenum(start_time)
                stop_dn = _datetime_to_matlab_datenum(stop_time)
                time_values = list(np.arange(start_dn, stop_dn, sample_interval_days))
            else:
                raise ValueError(f"No valid data rows found in {source_file}")

        time_arr = np.asarray(time_values, dtype=float)
        temp_arr = np.asarray(temp_values, dtype=float)
        pres_arr = np.asarray(pres_values, dtype=float)

        # --- Pressure: 65535 → NaN, bar → dbar (×10) ---
        # Mirrors MATLAB: pres(pres==65535)=NaN; pres=pres.*10;
        pres_arr[pres_arr == 65535] = np.nan
        pres_arr = pres_arr * 10.0

        # --- Burst averaging (mirrors MATLAB exactly) ---
        if is_burst and not is_averaged and samples_per_burst > 1:
            n_samples = len(time_arr)
            n_bursts = n_samples // samples_per_burst

            if n_bursts > 0:
                new_time = np.zeros(n_bursts)
                new_temp = np.zeros(n_bursts) if temp_idx is not None else np.array([])
                new_pres = np.zeros(n_bursts) if pres_idx is not None else np.array([])

                for k in range(n_bursts):
                    burst_start = k * samples_per_burst
                    burst_end = burst_start + samples_per_burst
                    new_time[k] = np.mean(time_arr[burst_start:burst_end])
                    if temp_idx is not None:
                        new_temp[k] = np.mean(temp_arr[burst_start:burst_end])
                    if pres_idx is not None:
                        new_pres[k] = np.mean(pres_arr[burst_start:burst_end])

                time_arr = new_time
                temp_arr = new_temp
                pres_arr = new_pres

        # --- Sample interval ---
        sample_interval_seconds = sample_interval_days * 24 * 3600
        if sample_interval_seconds <= 0 and len(time_arr) > 1:
            sample_interval_seconds = float(np.median(np.diff(time_arr) * 24 * 3600))

        # --- Build dataset (mirrors MATLAB structure) ---
        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", time_arr)

        # Scaffold variables
        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        coords = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"

        # TEMP variable (if present)
        if temp_idx is not None and temp_arr.size > 0:
            dataset.add_variable("TEMP", data=temp_arr, dims=["TIME"],
                                 attrs={"coordinates": coords})

        # PRES variable (if present and has valid data)
        if pres_idx is not None and pres_arr.size > 0 and np.any(~np.isnan(pres_arr)):
            dataset.add_variable("PRES", data=pres_arr, dims=["TIME"],
                                 attrs={"coordinates": coords})

        # Global attributes
        dataset.set_attrs({
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "Aquatec",
            "instrument_model": f"Aqualogger {model}" if model else "Aqualogger",
            "instrument_firmware": firmware,
            "instrument_serial_no": serial,
            "instrument_sample_interval": sample_interval_seconds,
            "parser": self.parser_name,
            "source_format": source_file.suffix.lower().lstrip("."),
        })

        return dataset


def _find_heading_index(heading: list[str], name: str) -> int | None:
    """Find index of a column name in the HEADING list (case-insensitive)."""
    for i, h in enumerate(heading):
        if h.lower() == name.lower():
            return i
    return None


def _parse_aquatec_datetime(value: str) -> datetime | None:
    """Parse Aquatec timestamp format: HH:MM:SS DD/MM/YYYY."""
    formats = ["%H:%M:%S %d/%m/%Y", "%H:%M:%S %d/%m/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _datetime_to_matlab_datenum(value: datetime) -> float:
    """Convert Python datetime to MATLAB datenum."""
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac

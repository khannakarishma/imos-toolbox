"""Shared parsing helpers for Star-Oddi DAT exports.

Full port of MATLAB GenericParser/InstrumentParsers/StaroddiParser.m including:
- Reconversion/dual-column support (TEMP/TEMP_2, PRES/PRES_REL)
- Fahrenheit detection from header channel/axis units
- Pressure offset correction → PRES_REL with applied_offset
- Temperature correction annotation
- PSAL_2 derivation when corrections are applied
- resolveIMOSName-style duplicate variable numbering
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from imos_toolbox.model import IMOSDataset

_VAR_MAP = {
    "temperature": "TEMP",
    "temp": "TEMP",
    "pressure": "PRES",
    "pres": "PRES",
    "depth": "DEPTH",
    "salinity": "PSAL",
    "sal": "PSAL",
    "conductivity": "CNDC",
    "soundvelocity": "SOUND_VEL",
    "soundvel": "SOUND_VEL",
    "roll": "ROLL",
    "pitch": "PITCH",
}


def parse_staroddi_dat(source_file: Path, mode: str, parser_name: str, default_model: str) -> IMOSDataset:
    """Parse a Star-Oddi DAT file into an IMOSDataset.
    
    Full port of MATLAB StaroddiParser.m including reconversion handling,
    Fahrenheit conversion, pressure offset, and temperature correction.
    """
    lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_lines = [line for line in lines if line.startswith("#")]
    data_lines = [line for line in lines if line.strip() and not line.startswith("#")]

    if not data_lines:
        raise ValueError(f"No Star-Oddi samples found in {source_file}")

    header = _parse_header(header_lines)
    time_values, values_by_var = _parse_data_rows(data_lines, header)

    if len(time_values) == 0:
        raise ValueError(f"No valid Star-Oddi rows found in {source_file}")

    # Determine instrument model (mirrors MATLAB)
    instrument_model = str(header.get("instrument_model", default_model))
    if default_model.lower().endswith("dst") and ("PITCH" in values_by_var or "ROLL" in values_by_var):
        instrument_model = "DST Tilt"

    # Build dataset with TIME as dimension (mirrors MATLAB loadTimeSeriesSampleTemplate)
    dataset = IMOSDataset.empty()
    dataset.add_dimension("TIME", np.asarray(time_values, dtype=float))
    
    # Scaffold variables
    dataset.add_variable(name="TIMESERIES", data=np.int32(1), dims=[])
    dataset.add_variable(name="LATITUDE", data=np.float64(np.nan), dims=[])
    dataset.add_variable(name="LONGITUDE", data=np.float64(np.nan), dims=[])
    dataset.add_variable(name="NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

    coords = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
    for var_name, values in values_by_var.items():
        if len(values) < len(time_values):
            values = np.concatenate([values, np.full(len(time_values) - len(values), np.nan)])
        dataset.add_variable(
            name=var_name,
            data=np.asarray(values[: len(time_values)], dtype=float),
            dims=["TIME"],
            attrs={"coordinates": coords},
        )

    # --- Fahrenheit conversion (mirrors MATLAB is_temp_fahrenheit logic) ---
    # MATLAB checks header channel_info_1.channel_units or axis_info_0.axis_units for '°F'
    is_fahrenheit = header.get("is_fahrenheit", False)
    if not is_fahrenheit:
        # Fallback: heuristic (median > 60 suggests Fahrenheit)
        for vn in [str(v) for v in dataset.dataset.data_vars]:
            if vn == "TEMP" or vn.startswith("TEMP_"):
                vals = dataset.dataset[vn].values
                finite = vals[np.isfinite(vals)]
                if finite.size > 0 and float(np.nanmedian(finite)) > 60.0:
                    is_fahrenheit = True
                    break
    
    if is_fahrenheit:
        for vn in [str(v) for v in dataset.dataset.data_vars]:
            if vn == "TEMP" or vn.startswith("TEMP_"):
                dataset.dataset[vn].values[:] = (dataset.dataset[vn].values - 32.0) * 5.0 / 9.0
                dataset.dataset[vn].attrs["comment"] = "Originaly expressed in Fahrenheit."

    # --- Temperature correction (mirrors MATLAB is_temp_corrected) ---
    is_temp_corrected = header.get("is_temp_corrected", False)
    if is_temp_corrected:
        if "TEMP_2" in dataset.dataset.data_vars:
            existing_comment = dataset.dataset["TEMP_2"].attrs.get("comment", "")
            dataset.dataset["TEMP_2"].attrs["comment"] = (
                existing_comment + "Normal temperature correction applied."
            )

    # --- Pressure offset correction → PRES_REL (mirrors MATLAB is_pres_corrected) ---
    is_pres_corrected = header.get("is_pres_corrected", False)
    pres_offset_mbar = header.get("pressure_offset_value", 0)
    
    if is_pres_corrected and "PRES" in dataset.dataset.data_vars:
        # Create PRES_REL from PRES data (mirrors MATLAB: copy PRES, rename to PRES_REL)
        pres_data = dataset.dataset["PRES"].values.copy()
        applied_offset = float(pres_offset_mbar) / 100.0  # mbar → dbar
        dataset.add_variable(
            name="PRES_REL",
            data=pres_data,
            dims=["TIME"],
            attrs={
                "coordinates": coords,
                "comment": f"A zero offset of value {pres_offset_mbar}mbar was adjusted.",
                "applied_offset": np.float32(applied_offset),
            },
        )
        
        # Also create DEPTH_2 if DEPTH exists (mirrors MATLAB)
        if "DEPTH" in dataset.dataset.data_vars:
            depth_data = dataset.dataset["DEPTH"].values.copy()
            dataset.add_variable(
                name="DEPTH_2",
                data=depth_data,
                dims=["TIME"],
                attrs={
                    "coordinates": coords,
                    "comment": f"A zero offset of value {pres_offset_mbar}mbar was adjusted to pressure.",
                },
            )

    # --- PSAL_2 when temp or pressure corrected (mirrors MATLAB is_salt_corrected) ---
    is_salt_corrected = (is_temp_corrected or is_pres_corrected) and "PSAL" in dataset.dataset.data_vars
    if is_salt_corrected:
        psal_data = dataset.dataset["PSAL"].values.copy()
        psal_comment = ""
        if is_temp_corrected:
            psal_comment += "Normal temperature correction applied."
        if is_pres_corrected:
            psal_comment += f"A zero offset of value {pres_offset_mbar}mbar was adjusted to pressure."
        dataset.add_variable(
            name="PSAL_2",
            data=psal_data,
            dims=["TIME"],
            attrs={"coordinates": coords, "comment": psal_comment},
        )

    # Global attributes
    attrs: dict[str, Any] = {
        "toolbox_input_file": str(source_file),
        "featureType": mode,
        "instrument_make": "Star ODDI",
        "instrument_model": instrument_model,
        "instrument_serial_no": str(header.get("serial_no", "")),
        "parser": parser_name,
        "source_format": source_file.suffix.lower().lstrip("."),
    }
    if len(time_values) > 1:
        attrs["instrument_sample_interval"] = float(
            np.median(np.diff(np.asarray(time_values, dtype=float))) * 24.0 * 3600.0
        )

    dataset.set_attrs(attrs)
    return dataset


def _parse_header(lines: list[str]) -> dict[str, Any]:
    """Parse Star-Oddi DAT header lines.
    
    Extracts recorder info, date/time format, reconversion flag,
    temperature correction flag, pressure offset, and channel units.
    """
    header: dict[str, Any] = {
        "is_date_joined": True,
        "date_format": "dd/mm/yyyy",
        "time_format": "HH:MM:SS",
        "is_fahrenheit": False,
        "is_temp_corrected": False,
        "is_pres_corrected": False,
        "pressure_offset_value": 0,
        "reconversion": False,
    }

    recorder_expr = re.compile(
        r"(?:#\t)?Recorder(?:\s*:\s*|\t)(\S+)(?:\t([^\t]+))?(?:\t([^\t]+))?", re.IGNORECASE
    )
    date_time_expr = re.compile(r"Date\s*&\s*Time:\s*(\d+)", re.IGNORECASE)
    date_def_expr = re.compile(r"Date def\.:\s*([^\t/]+)", re.IGNORECASE)
    time_def_expr = re.compile(r"Time def\.:\s*(\d+)", re.IGNORECASE)
    reconvert_expr = re.compile(r"Reconvert", re.IGNORECASE)
    temp_corr_expr = re.compile(r"No temperature correction", re.IGNORECASE)
    pres_offset_expr = re.compile(r"Pressure offset correction:\s*([\d.]+)", re.IGNORECASE)
    # Channel/Axis units for Fahrenheit detection
    channel_units_expr = re.compile(r"(?:Channel|Axis)\s+\d+.*?(?:°F|degF|\xb0F)", re.IGNORECASE)

    for line in lines:
        stripped = line.lstrip("#").strip()

        # Recorder info
        recorder = recorder_expr.search(line)
        if recorder:
            groups = [g for g in recorder.groups() if g]
            if len(groups) >= 1:
                if groups[0].isdigit():
                    header["serial_no"] = groups[0]
                    if len(groups) >= 2:
                        header["instrument_model"] = groups[1].strip()
                else:
                    header["instrument_model"] = groups[0].strip()
                    if len(groups) >= 2 and groups[1].strip().replace("-", "").isdigit():
                        header["serial_no"] = groups[1].strip()
            continue

        # Date/time format
        match = date_time_expr.search(stripped)
        if match:
            header["is_date_joined"] = match.group(1) != "0"
            continue

        match = date_def_expr.search(stripped)
        if match:
            header["date_format"] = match.group(1).strip()
            continue

        match = time_def_expr.search(stripped)
        if match:
            header["time_format"] = "HH:MM:SS" if match.group(1) == "0" else "HH.MM.SS"
            continue

        # Reconversion flag (mirrors MATLAB: hinfo.reconvertion)
        if reconvert_expr.search(stripped):
            if "yes" in stripped.lower() or "true" in stripped.lower() or "1" in stripped:
                header["reconversion"] = True
            continue

        # Temperature correction flag (mirrors MATLAB: hinfo.no_temperature_correction)
        # If "No temperature correction" is NOT present → correction WAS applied
        if temp_corr_expr.search(stripped):
            # Line says "No temperature correction: No" → correction applied
            if "no" in stripped.split(":")[-1].strip().lower():
                header["is_temp_corrected"] = True
            continue

        # Pressure offset correction
        match = pres_offset_expr.search(stripped)
        if match:
            offset_val = float(match.group(1))
            if offset_val != 0:
                header["is_pres_corrected"] = True
                header["pressure_offset_value"] = offset_val
            continue

        # Fahrenheit detection from channel/axis units
        if channel_units_expr.search(stripped):
            header["is_fahrenheit"] = True

    return header


def _parse_data_rows(
    lines: list[str], header: dict[str, Any]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Parse Star-Oddi data rows into time + variables.
    
    Handles reconverted files with dual columns (raw + converted per channel)
    and resolves duplicate IMOS names (TEMP → TEMP, TEMP_2, etc.).
    """
    times: list[float] = []
    by_var: dict[str, list[float]] = {}

    for line in lines:
        parts = [token for token in re.split(r"\s+", line.strip()) if token]
        if len(parts) < 3:
            continue

        idx = 1  # first token is sample number

        date_text = parts[idx]
        time_text = parts[idx + 1]
        value_start = idx + 2

        dt = _parse_datetime(date_text, time_text)
        if dt is None:
            continue

        numeric_tokens = parts[value_start:]
        parsed_values = []
        for token in numeric_tokens:
            cleaned = token.replace(",", ".")
            try:
                parsed_values.append(float(cleaned))
            except ValueError:
                parsed_values.append(np.nan)

        times.append(_datetime_to_matlab_datenum(dt))

        if not by_var:
            for col_idx in range(len(parsed_values)):
                by_var[f"col_{col_idx+1}"] = []

        for key in by_var:
            by_var[key].append(np.nan)

        for col_idx, value in enumerate(parsed_values):
            raw_name = f"col_{col_idx+1}"
            if raw_name in by_var:
                by_var[raw_name][-1] = value

    # Map columns to IMOS variable names using header channel/axis info
    # Mirrors MATLAB: convertVariables with resolveIMOSName for duplicates
    mapped_by_var: dict[str, np.ndarray] = {}
    existing_names: list[str] = []
    ordered_keys = sorted(by_var.keys(), key=lambda k: int(k.split("_")[1]))
    
    for key in ordered_keys:
        col_num = int(key.split("_")[1])
        name_guess = _guess_var_name(lines, col_num)
        var_name = _normalize_var(name_guess) if name_guess else ""
        if not var_name:
            continue

        values = np.asarray(by_var[key], dtype=float)

        # Resolve duplicate names (mirrors MATLAB resolveIMOSName)
        resolved = _resolve_imos_name(existing_names, var_name)
        existing_names.append(resolved)
        mapped_by_var[resolved] = values

    return np.asarray(times, dtype=float), mapped_by_var


def _resolve_imos_name(existing: list[str], name: str) -> str:
    """Resolve duplicate variable names (mirrors MATLAB resolveIMOSName).
    
    First occurrence: TEMP
    Second occurrence: TEMP_2
    Third occurrence: TEMP_3
    """
    if name not in existing:
        return name
    suffix = 2
    while f"{name}_{suffix}" in existing:
        suffix += 1
    return f"{name}_{suffix}"


def _guess_var_name(lines: list[str], column_index: int) -> str:
    """Guess variable name from header Channel/Axis lines.
    
    Mirrors MATLAB selectChannelOrAxisName: checks channel_index_N (Mini)
    and axis_index_N (DST, 0-based).
    """
    # Starmon Mini: "Channel N: Temperature(°C)" pattern
    channel_pattern = re.compile(
        rf"Channel\s+{column_index}\s*[:\t]\s*([^\(\t#]+)", re.IGNORECASE
    )
    # DST: "Axis N ..." pattern (0-based: column 1 → axis 0)
    axis_pattern = re.compile(
        rf"Axis\s*\t?\s*{column_index - 1}\s*[\t:]\s*([^\(\t#]+)", re.IGNORECASE
    )

    for line in lines:
        raw = line.lstrip("#")
        match = channel_pattern.search(raw)
        if match:
            return match.group(1).strip()
        match = axis_pattern.search(raw)
        if match:
            return match.group(1).strip()
    return ""


def _normalize_var(value: str) -> str:
    """Normalize a channel/axis name to an IMOS variable name."""
    key = re.sub(r"[^a-zA-Z]", "", value).lower()
    return _VAR_MAP.get(key, "")


def _parse_datetime(date_text: str, time_text: str) -> datetime | None:
    """Parse Star-Oddi date and time strings."""
    combos = [
        "%d.%m.%y %H:%M:%S",
        "%m.%d.%y %H:%M:%S",
        "%d/%m/%y %H:%M:%S",
        "%m/%d/%y %H:%M:%S",
        "%d-%m-%y %H:%M:%S",
        "%m-%d-%y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
    ]

    normalized_time = time_text.replace(".", ":")
    text = f"{date_text} {normalized_time}"
    for fmt in combos:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac

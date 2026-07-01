"""Aquatec parser implementation (initial AQUAlogger key-value format support)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser


class AquatecParser(BaseParser):
    """Parser for Aquatec AQUAlogger exports."""

    parser_name = "aquatec"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("aquatec parser currently expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() not in {".txt", ".dat", ".csv"}:
            raise ValueError("aquatec parser currently supports .txt/.dat/.csv files")

        meta, heading, data_lines = _read_sections(source_file)
        if not data_lines:
            raise ValueError(f"No Aquatec DATA rows found in {source_file}")

        time_values, temp_values, pres_values = _parse_data_rows(data_lines, heading)
        if len(time_values) == 0:
            raise ValueError(f"No valid Aquatec rows found in {source_file}")

        # Burst-mode averaging (mirrors MATLAB aquatecParse.m)
        # If instrument is in burst mode and data is not pre-averaged,
        # group samples into bursts and compute mean per burst.
        is_burst_mode = "burst" in meta.get("REGIME", "").lower()
        is_pre_averaged = meta.get("AVERAGED", "").strip().lower() == "yes"
        samples_per_burst = _get_samples_per_burst(meta)

        if is_burst_mode and not is_pre_averaged and samples_per_burst > 1:
            time_values, temp_values, pres_values = _burst_average(
                time_values, temp_values, pres_values, samples_per_burst
            )

        # Sentinel value: pressure 65535 → NaN (mirrors MATLAB)
        pres_values[pres_values >= 65535] = np.nan

        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", np.asarray(time_values, dtype=float))
        dataset.add_variable(name="TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable(name="LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable(name="LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable(name="NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        coords = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
        if temp_values.size > 0 and np.any(np.isfinite(temp_values)):
            dataset.add_variable(name="TEMP", data=temp_values, dims=["TIME"],
                                 attrs={"coordinates": coords})
        if pres_values.size > 0 and np.any(np.isfinite(pres_values)):
            dataset.add_variable(name="PRES", data=pres_values, dims=["TIME"],
                                 attrs={"coordinates": coords})

        attrs: dict[str, str | float] = {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "Aquatec",
            "instrument_model": _instrument_model(meta),
            "instrument_firmware": meta.get("VERSION", ""),
            "instrument_serial_no": _instrument_serial(meta),
            "parser": self.parser_name,
            "source_format": source_file.suffix.lower().lstrip("."),
        }

        sample_interval = _sample_interval_seconds(meta)
        if sample_interval is not None and sample_interval > 0:
            attrs["instrument_sample_interval"] = sample_interval
        elif len(time_values) > 1:
            attrs["instrument_sample_interval"] = float(np.median(np.diff(np.asarray(time_values, dtype=float))) * 24.0 * 3600.0)

        dataset.set_attrs(attrs)
        return dataset


def _read_sections(source_file: Path) -> tuple[dict[str, str], list[str], list[str]]:
    meta: dict[str, str] = {}
    heading: list[str] = []
    data_lines: list[str] = []

    for line in source_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("DATA"):
            data_lines.append(stripped)
            continue

        key, _, remainder = stripped.partition(",")
        key = key.strip().upper()
        remainder = remainder.strip()
        if key == "HEADING":
            heading = [token.strip() for token in remainder.split(",")]
        else:
            meta[key] = remainder

    return meta, heading, data_lines


def _parse_data_rows(data_lines: list[str], heading: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lower_head = [h.lower() for h in heading]
    has_temp = any("ext temperature" in h for h in lower_head)
    has_pres = any(h == "pressure" for h in lower_head)

    time_values: list[float] = []
    temp_values: list[float] = []
    pres_values: list[float] = []

    for line in data_lines:
        parts = [token.strip() for token in line.split(",")]
        if len(parts) < 2:
            continue

        dt_text = parts[1]
        dt = _parse_aquatec_datetime(dt_text)
        if dt is None:
            continue

        values = parts[2:]
        time_values.append(_datetime_to_matlab_datenum(dt))

        temp_val = np.nan
        pres_val = np.nan

        if has_temp and len(values) >= 2:
            try:
                temp_val = float(values[1])
            except ValueError:
                temp_val = np.nan

        if has_pres and len(values) >= 4:
            try:
                pres_bar = float(values[3])
                if np.isfinite(pres_bar):
                    pres_val = pres_bar * 10.0
            except ValueError:
                pres_val = np.nan

        temp_values.append(temp_val)
        pres_values.append(pres_val)

    return np.asarray(time_values, dtype=float), np.asarray(temp_values, dtype=float), np.asarray(pres_values, dtype=float)


def _instrument_model(meta: dict[str, str]) -> str:
    logger_type = meta.get("LOGGER TYPE", "")
    model = logger_type
    for token in ("Pressure & Temperature", "Pressure", "Temperature"):
        model = model.replace(token, "")
    model = model.strip()
    if model:
        return f"Aqualogger {model}"
    return "Aqualogger"


def _instrument_serial(meta: dict[str, str]) -> str:
    logger = meta.get("LOGGER", "")
    return logger.split(",")[0].strip() if logger else ""


def _sample_interval_seconds(meta: dict[str, str]) -> float | None:
    regime = meta.get("REGIME", "")
    if not regime:
        return None

    tokens = [token.strip() for token in regime.split(",") if token.strip()]
    if len(tokens) < 2:
        return None

    amount_match = re.search(r"[-+]?\d*\.?\d+", tokens[1])
    if not amount_match:
        return None

    amount = float(amount_match.group(0))
    unit = tokens[1].lower()
    if "minute" in unit:
        return amount * 60.0
    return amount


def _parse_aquatec_datetime(value: str) -> datetime | None:
    formats = ["%H:%M:%S %d/%m/%Y", "%H:%M:%S %d/%m/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac


def _get_samples_per_burst(meta: dict[str, str]) -> int:
    """Extract samples-per-burst from REGIME field.
    
    Mirrors MATLAB aquatecParse.m: parses 'Burst Mode, N samples' from REGIME.
    """
    regime = meta.get("REGIME", "")
    match = re.search(r"(\d+)\s*sample", regime, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 1


def _burst_average(
    time: np.ndarray,
    temp: np.ndarray,
    pres: np.ndarray,
    samples_per_burst: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average burst samples into single values per burst.
    
    Mirrors MATLAB aquatecParse.m burst-mode averaging logic:
    groups of `samples_per_burst` consecutive samples are averaged
    into single representative values.
    """
    n = len(time)
    n_bursts = n // samples_per_burst
    if n_bursts == 0:
        return time, temp, pres
    
    # Trim to complete bursts
    trim = n_bursts * samples_per_burst
    time_reshaped = time[:trim].reshape(n_bursts, samples_per_burst)
    temp_reshaped = temp[:trim].reshape(n_bursts, samples_per_burst)
    pres_reshaped = pres[:trim].reshape(n_bursts, samples_per_burst)
    
    # Mean of each burst (matches MATLAB mean())
    avg_time = np.nanmean(time_reshaped, axis=1)
    avg_temp = np.nanmean(temp_reshaped, axis=1)
    avg_pres = np.nanmean(pres_reshaped, axis=1)
    
    return avg_time, avg_temp, avg_pres

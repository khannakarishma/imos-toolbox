"""JFE Infinity SD Logger CSV parser.

Port of MATLAB `infinitySDLoggerParse.m`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser

_COORDS = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"


@dataclass
class _InfinityVar:
    name: str
    values: np.ndarray
    comment: str


class InfinitySDParser(BaseParser):
    """Parser for JFE Infinity SD Logger CSV files."""

    parser_name = "InfinitySD"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("InfinitySD parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".csv":
            raise ValueError("InfinitySD parser supports .csv files only")

        lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        header, item_columns, data_rows = _split_sections(lines, source_file)
        time_values, variables = _read_data(item_columns, data_rows, source_file)

        if time_values.size < 1:
            raise ValueError(f"No valid InfinitySD samples found in {source_file}")

        corrected_time = _fix_repeated_times_jfe(time_values)

        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", corrected_time.astype(float))

        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        for variable in variables:
            variable_attrs: dict[str, str] = {"coordinates": _COORDS}
            if variable.comment:
                variable_attrs["comment"] = variable.comment
            dataset.add_variable(
                name=variable.name,
                data=variable.values.astype(float),
                dims=["TIME"],
                attrs=variable_attrs,
            )

        dataset_attrs: dict[str, str | float] = {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "JFE",
            "instrument_model": header.get("SondeName", ""),
            "instrument_serial_no": header.get("SondeNo", ""),
            "parser": self.parser_name,
            "source_format": "csv",
        }
        if corrected_time.size > 1:
            dataset_attrs["instrument_sample_interval"] = float(
                np.median(np.diff(corrected_time) * 24.0 * 3600.0)
            )

        dataset.set_attrs(dataset_attrs)
        return dataset


def _split_sections(
    lines: list[str], source_file: Path
) -> tuple[dict[str, str], list[str], list[list[str]]]:
    head_start = None
    item_start = None
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line == "[Head]":
            head_start = idx + 1
        elif line == "[Item]":
            item_start = idx
            break

    if head_start is None or item_start is None:
        raise ValueError(f"InfinitySD file missing [Head]/[Item] sections: {source_file}")
    if item_start <= head_start:
        raise ValueError(f"InfinitySD header section malformed: {source_file}")

    header: dict[str, str] = {}
    for raw_line in lines[head_start:item_start]:
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        header[key.strip()] = value.strip()

    if item_start + 1 >= len(lines):
        raise ValueError(f"InfinitySD file has no item header row: {source_file}")

    item_columns = _csv_tokens(lines[item_start + 1])
    if not item_columns:
        raise ValueError(f"InfinitySD item header row is empty: {source_file}")

    data_rows: list[list[str]] = []
    for raw_line in lines[item_start + 2 :]:
        if not raw_line.strip():
            continue
        row = _csv_tokens(raw_line)
        if row:
            data_rows.append(row)

    return header, item_columns, data_rows


def _read_data(
    item_columns: list[str], data_rows: list[list[str]], source_file: Path
) -> tuple[np.ndarray, list[_InfinityVar]]:
    col_index = {name.strip(): idx for idx, name in enumerate(item_columns)}

    time_idx = _find_index(col_index, ["Date", "Meas date"])
    if time_idx is None:
        raise ValueError(f"InfinitySD file missing date column: {source_file}")

    mappings = [
        (["Temp.[deg C]", "Temp.[degC]"], "TEMP", ""),
        (
            ["Chl-a[ug/l]"],
            "CPHL",
            (
                "Artificial chlorophyll data computed from bio-optical sensor raw counts "
                "measurements. The fluorometre is equipped with a 470nm peak wavelength LED "
                "to irradiate and a photodetector paired with an optical filter which "
                "measures everything that fluoresces in the region of 650nm to 1000nm. "
                "Originally expressed in ug/l, 1l = 0.001m3 was assumed."
            ),
        ),
        (
            ["Turb. -M[FTU]", "Turb.-M[FTU]"],
            "TURBF",
            (
                "Turbidity data computed from bio-optical sensor raw counts measurements. "
                "The turbidity sensor is equipped with a 880nm peak wavelength LED to "
                "irradiate and a photodetector paired with an optical filter which measures "
                "everything that backscatters in the region of 650nm to 1000nm."
            ),
        ),
        (["Batt.[V]"], "BAT_VOLT", ""),
    ]

    map_indexes: list[tuple[int, str, str]] = []
    for aliases, out_name, comment in mappings:
        idx = _find_index(col_index, aliases)
        if idx is not None:
            map_indexes.append((idx, out_name, comment))

    if not map_indexes:
        raise ValueError(f"No known InfinitySD variables found in {source_file}")

    times: list[float] = []
    values: dict[str, list[float]] = {out_name: [] for _, out_name, _ in map_indexes}
    comments: dict[str, str] = {out_name: comment for _, out_name, comment in map_indexes}

    for row in data_rows:
        if time_idx >= len(row):
            continue

        dt_text = row[time_idx].strip()
        dt = _parse_timestamp(dt_text)
        if dt is None:
            continue

        parsed: dict[str, float] = {}
        is_valid = True
        for idx, out_name, _ in map_indexes:
            if idx >= len(row):
                is_valid = False
                break
            try:
                parsed[out_name] = float(row[idx])
            except ValueError:
                is_valid = False
                break
        if not is_valid:
            continue

        times.append(_datetime_to_matlab_datenum(dt))
        for out_name in values:
            values[out_name].append(parsed[out_name])

    if not times:
        raise ValueError(f"No parseable InfinitySD samples found in {source_file}")

    variables = [
        _InfinityVar(name=name, values=np.asarray(v, dtype=float), comment=comments[name])
        for name, v in values.items()
    ]
    return np.asarray(times, dtype=float), variables


def _find_index(columns: dict[str, int], aliases: list[str]) -> int | None:
    for name in aliases:
        if name in columns:
            return columns[name]
    return None


def _csv_tokens(line: str) -> list[str]:
    row = next(csv.reader([line], delimiter=","))
    while row and row[-1].strip() == "":
        row.pop()
    return [item.strip() for item in row]


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac


def _find_repeats(arr: np.ndarray) -> list[tuple[int, int, int]]:
    """Return ``(start, end_inclusive, length)`` for each run of >=2 equal values.

    Faithful port of MATLAB `Util/findRepeats.m`: the input must be sorted and
    singleton values (runs of length 1) are skipped.
    """
    runs: list[tuple[int, int, int]] = []
    n = arr.size
    i = 0
    while i < n:
        j = i
        while j + 1 < n and arr[j + 1] == arr[i]:
            j += 1
        length = j - i + 1
        if length >= 2:
            runs.append((i, j, length))
        i = j + 1
    return runs


def _fix_repeated_times_jfe(time_values: np.ndarray) -> np.ndarray:
    """Restore sub-second spacing for repeated JFE timestamps.

    Faithful port of MATLAB `Util/fixRepeatedTimesJFE.m`. JFE Infinity loggers
    clip timestamp precision when configured for sub-second sampling, producing
    runs of identical datenum values. The missing sub-second offsets are
    redistributed within each repeated run.

    The first and last bursts are treated as the truncated tail/head of a full
    burst, so they are aligned to the end/start of the full sub-second grid
    (built from the global maximum repeat count), exactly as MATLAB does.
    Interior bursts span their own length.
    """
    time = np.asarray(time_values, dtype=float)
    n = time.size
    if n < 2:
        return time
    if np.any(np.diff(time) < 0):
        raise ValueError("InfinitySD time values are not sorted")

    # `unique(diff(time))` is sorted ascending, matching timeSamplingInfo.sampling_steps.
    steps = np.unique(np.diff(time))
    if np.all(steps == 0):
        raise ValueError("InfinitySD time values are constant and cannot be corrected")
    if steps[0] != 0:
        # No repeated samples -> nothing to correct.
        return time

    # sampling_steps(2): smallest positive step == burst sampling interval.
    freq = float(steps[1])

    runs = _find_repeats(time)
    if not runs:
        return time

    nrepeats = [length for _, _, length in runs]
    distinct_repeats = sorted(set(nrepeats))
    if len(distinct_repeats) > 3:
        # MATLAB `wildly_repeated` guard.
        raise ValueError(
            "InfinitySD repeated-time correction: too many distinct repeat counts "
            f"{distinct_repeats}"
        )
    maxrepeat = max(distinct_repeats)

    def partial_time(f: float, nr: int) -> np.ndarray:
        return f * np.arange(nr, dtype=float) / float(nr)

    newtime = np.zeros(n, dtype=float)

    # Boundary conditions: full sub-second grid for the global max repeat count.
    ztime = partial_time(freq, maxrepeat)
    first_start, first_end, first_len = runs[0]
    last_start, last_end, last_len = runs[-1]
    # First (possibly truncated) burst is the tail of a full burst.
    newtime[first_start : first_end + 1] = ztime[maxrepeat - first_len :]
    # Last (possibly truncated) burst is the head of a full burst.
    newtime[last_start : last_end + 1] = ztime[:last_len]

    # Interior bursts span their own length.
    for start, end, length in runs[1:-1]:
        newtime[start : end + 1] = partial_time(freq, length)

    newtime = newtime + time
    if np.any(np.diff(newtime) < 0):
        raise ValueError("InfinitySD repeated-time correction failed")

    return newtime

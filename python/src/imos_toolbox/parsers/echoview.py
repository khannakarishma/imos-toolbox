"""Echoview CSV export parser.

Port of MATLAB `echoviewParse.m`.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser

_DEFAULT_FIELD_MAP_ROWS = [
    "processing_software_version_38,Program_version,,S",
    "frequency_38,Frequency,,N",
    "TIME,Date_M,,DT,ones(size(TIME))",
    "DEPTH,Layer_depth,,N,ones(size(DEPTH))",
    "LATITUDE,Lat_M,TIME,N,ones(size(LATITUDE))",
    "LONGITUDE,Lon_M,TIME,N,ones(size(LONGITUDE))",
    "Sv_38,Sv_mean,TIME DEPTH,N,(2 - ((Sv_38 < 0) & (Sv_pcnt_good_38 > 50))) * 2",
    "Sv_pcnt_good_38,Pct_good,TIME DEPTH,N",
    "Sv_sd_38,Standard_deviation,TIME DEPTH,N",
    "Sv_skew_38,Skewness,TIME DEPTH,N",
    "Sv_kurt_38,Kurtosis,TIME DEPTH,N",
    "mean_height_38,Height_mean,TIME DEPTH,N",
    "mean_depth_38,Depth_mean,TIME DEPTH,N",
    "Sv_unfilt_38,Uncleaned_Sv_mean,TIME DEPTH,N",
    "Sv_unfilt_sd_38,Uncleaned_Standard_deviation,TIME DEPTH,N",
    "Sv_unfilt_skew_38,Uncleaned_Skewness,TIME DEPTH,N",
    "Sv_unfilt_kurt_38,Uncleaned_Kurtosis,TIME DEPTH,N",
]


@dataclass
class _FieldMapEntry:
    name: str
    column_name: str
    dimensions: list[str]
    field_type: str
    qc_expression: str | None
    column_index: int = -1

    @property
    def is_dimension(self) -> bool:
        return len(self.dimensions) == 0


@dataclass
class _ParsedRow:
    dimensions: dict[str, Any]
    variables: dict[str, Any]


class EchoviewParser(BaseParser):
    """Parser for Echoview CSV exports."""

    parser_name = "Echoview"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Echoview parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".csv":
            raise ValueError("Echoview parser supports .csv files only")

        field_map = _load_field_map()
        if not field_map:
            raise ValueError("Echoview field map is empty")

        with source_file.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            rows = list(csv.reader(handle))
        if not rows:
            raise ValueError(f"Echoview file is empty: {source_file}")

        header = [_sanitize_header_token(token) for token in rows[0]]
        _bind_columns(field_map, header)

        usable_entries = [entry for entry in field_map if entry.column_index >= 0]
        if not usable_entries:
            raise ValueError(
                "Echoview CSV columns do not match configured field map. "
                f"Header columns: {header}"
            )

        dimension_entries = [entry for entry in usable_entries if entry.is_dimension]
        variable_entries = [entry for entry in usable_entries if not entry.is_dimension]

        if not any(entry.name == "TIME" for entry in dimension_entries):
            raise ValueError("Echoview parser requires TIME dimension column(s)")

        parsed_rows: list[_ParsedRow] = []
        dim_values: dict[str, list[Any]] = {entry.name: [] for entry in dimension_entries}
        dim_indexes: dict[str, dict[str, int]] = {entry.name: {} for entry in dimension_entries}

        for row in rows[1:]:
            if len(row) < 4:
                continue

            parsed_dims: dict[str, Any] = {}
            for entry in dimension_entries:
                value = _parse_field(row, entry)
                parsed_dims[entry.name] = value
                key = _value_key(value)
                if key not in dim_indexes[entry.name]:
                    dim_indexes[entry.name][key] = len(dim_values[entry.name])
                    dim_values[entry.name].append(value)

            parsed_vars: dict[str, Any] = {}
            for entry in variable_entries:
                parsed_vars[entry.name] = _parse_field(row, entry)

            parsed_rows.append(_ParsedRow(dimensions=parsed_dims, variables=parsed_vars))

        if not parsed_rows:
            raise ValueError(f"No parseable Echoview rows found in {source_file}")

        dataset = IMOSDataset.empty()

        non_singleton_dims = {
            name: values for name, values in dim_values.items() if len(values) > 1
        }
        singleton_dims = {
            name: values[0] for name, values in dim_values.items() if len(values) == 1
        }

        for entry in dimension_entries:
            if entry.name in non_singleton_dims:
                dim_coord_values = non_singleton_dims[entry.name]
                if entry.field_type == "S":
                    dataset.add_dimension(entry.name, np.asarray(dim_coord_values, dtype=object))
                else:
                    dataset.add_dimension(entry.name, np.asarray(dim_coord_values, dtype=float))
            elif entry.name in singleton_dims:
                dataset.add_variable(entry.name, data=_to_scalar(singleton_dims[entry.name]), dims=[])

        var_defs: dict[str, tuple[list[str], np.ndarray]] = {}
        for entry in variable_entries:
            var_dims = [dim for dim in entry.dimensions if dim in non_singleton_dims]
            shape = tuple(len(non_singleton_dims[dim]) for dim in var_dims)

            var_data: np.ndarray
            if entry.field_type == "S":
                var_data = np.empty(shape if shape else (), dtype=object)
                if shape:
                    var_data.fill("")
                else:
                    var_data = np.asarray("", dtype=object)
            else:
                if shape:
                    var_data = np.full(shape, np.nan, dtype=float)
                else:
                    var_data = np.asarray(np.nan, dtype=float)
            var_defs[entry.name] = (var_dims, var_data)

        for parsed in parsed_rows:
            for entry in variable_entries:
                var_dims, var_data = var_defs[entry.name]
                value = parsed.variables[entry.name]
                dim_index = {
                    dim_name: dim_indexes[dim_name][_value_key(parsed.dimensions[dim_name])]
                    for dim_name in entry.dimensions
                    if dim_name in non_singleton_dims
                }
                if var_dims:
                    idx = tuple(dim_index[dim_name] for dim_name in var_dims)
                    var_data[idx] = value
                else:
                    var_data = np.asarray(value)
                var_defs[entry.name] = (var_dims, var_data)

        for entry in variable_entries:
            var_dims, var_data = var_defs[entry.name]
            variable_attrs = {"coordinates": " ".join(var_dims)} if var_dims else None
            dataset.add_variable(
                entry.name,
                data=var_data,
                dims=var_dims,
                attrs=variable_attrs,
            )

        _apply_qc(dataset, usable_entries)

        dataset_attrs: dict[str, Any] = {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": "Simrad",
            "instrument_model": "ES60",
            "instrument_serial_no": "",
            "site_code": "SOOP-BA",
            "level": 2,
            "EV_csv_file": source_file.name,
            "parser": self.parser_name,
            "source_format": "csv",
        }

        # Extract instrument metadata from singleton variables (mirrors MATLAB)
        if "make" in dataset.dataset.data_vars:
            dataset_attrs["instrument_make"] = str(dataset.dataset["make"].values)
        if "sounder" in dataset.dataset.data_vars:
            dataset_attrs["instrument_model"] = str(dataset.dataset["sounder"].values)
        if "channel" in dataset.dataset.data_vars:
            dataset_attrs["instrument_serial_no"] = str(dataset.dataset["channel"].values)

        # vessel_name → site_name (mirrors MATLAB getPlatform/getAttributes)
        if "vessel_name" in dataset.dataset.data_vars:
            dataset_attrs["site_name"] = str(dataset.dataset["vessel_name"].values)

        # frequency → depth metadata (mirrors MATLAB field mapping)
        if "frequency_38" in dataset.dataset.data_vars:
            freq_val = dataset.dataset["frequency_38"].values
            if np.isscalar(freq_val) or freq_val.size == 1:
                dataset_attrs["instrument_frequency"] = float(freq_val)

        # Compute geospatial/temporal bounds (mirrors MATLAB getBounds)
        _compute_bounds(dataset, dataset_attrs)

        dataset.set_attrs(dataset_attrs)
        return dataset


def _compute_bounds(dataset: IMOSDataset, attrs: dict[str, Any]) -> None:
    """Compute geospatial and temporal coverage bounds.
    
    Mirrors MATLAB echoviewParse.getBounds(): derives time_coverage_start/end,
    geospatial_lat/lon_min/max, and geospatial_vertical_min/max from the data.
    """
    ds = dataset.dataset
    
    # Time bounds
    if "TIME" in ds.dims:
        time_vals = ds.coords["TIME"].values
        valid_time = time_vals[np.isfinite(time_vals)]
        if len(valid_time) > 0:
            attrs["time_coverage_start"] = float(np.min(valid_time))
            attrs["time_coverage_end"] = float(np.max(valid_time))
    
    # Latitude bounds
    if "LATITUDE" in ds.data_vars:
        lat_vals = ds["LATITUDE"].values.ravel()
        valid_lat = lat_vals[np.isfinite(lat_vals)]
        if len(valid_lat) > 0:
            attrs["geospatial_lat_min"] = float(np.min(valid_lat))
            attrs["geospatial_lat_max"] = float(np.max(valid_lat))
    
    # Longitude bounds
    if "LONGITUDE" in ds.data_vars:
        lon_vals = ds["LONGITUDE"].values.ravel()
        valid_lon = lon_vals[np.isfinite(lon_vals)]
        if len(valid_lon) > 0:
            attrs["geospatial_lon_min"] = float(np.min(valid_lon))
            attrs["geospatial_lon_max"] = float(np.max(valid_lon))
    
    # Depth/vertical bounds
    if "DEPTH" in ds.dims:
        depth_vals = ds.coords["DEPTH"].values
        valid_depth = depth_vals[np.isfinite(depth_vals)]
        if len(valid_depth) > 0:
            attrs["geospatial_vertical_min"] = float(np.min(valid_depth))
            attrs["geospatial_vertical_max"] = float(np.max(valid_depth))


def _load_field_map() -> list[_FieldMapEntry]:
    config_path = Path(__file__).resolve().parents[4] / "Parser" / "echoview_config.txt"
    lines: list[str]
    if config_path.exists():
        lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    else:
        lines = _DEFAULT_FIELD_MAP_ROWS

    entries: list[_FieldMapEntry] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("%"):
            continue
        row = [token.strip() for token in next(csv.reader([line]))]
        if len(row) < 4:
            continue
        name, column_name, dimensions_text, field_type = row[:4]
        qc_expression = ",".join(row[4:]).strip() if len(row) > 4 else ""
        dimensions = [token for token in dimensions_text.split() if token]
        entries.append(
            _FieldMapEntry(
                name=name,
                column_name=column_name,
                dimensions=dimensions,
                field_type=field_type,
                qc_expression=qc_expression if qc_expression else None,
            )
        )
    return entries


def _bind_columns(field_map: list[_FieldMapEntry], header: list[str]) -> None:
    lookup = {name: idx for idx, name in enumerate(header)}
    for entry in field_map:
        entry.column_index = lookup.get(entry.column_name, -1)


def _parse_field(row: list[str], entry: _FieldMapEntry) -> Any:
    idx = entry.column_index
    if idx < 0 or idx >= len(row):
        return np.nan if entry.field_type != "S" else ""

    value = row[idx].strip()
    if entry.field_type == "S":
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value
    if entry.field_type == "N":
        return _to_float(value)
    if entry.field_type == "D":
        try:
            dt = datetime.strptime(value, "%Y%m%d")
        except ValueError:
            return np.nan
        return _datetime_to_matlab_datenum(dt)
    if entry.field_type == "T":
        return _time_to_day_fraction(value)
    if entry.field_type == "DT":
        if idx + 1 >= len(row):
            return np.nan
        time_value = row[idx + 1].strip()
        return _parse_datetime_pair(value, time_value)
    return np.nan


def _parse_datetime_pair(date_text: str, time_text: str) -> float:
    if len(date_text) < 8:
        return np.nan
    try:
        year = int(date_text[0:4])
        month = int(date_text[4:6])
        day = int(date_text[6:8])
    except ValueError:
        return np.nan

    try:
        # MATLAB appends a trailing 0 and parses HH:MM:SS.FFF
        parsed_time = datetime.strptime(f"{time_text}0", "%H:%M:%S.%f")
    except ValueError:
        try:
            parsed_time = datetime.strptime(time_text, "%H:%M:%S")
        except ValueError:
            return np.nan

    dt = datetime(
        year,
        month,
        day,
        parsed_time.hour,
        parsed_time.minute,
        parsed_time.second,
        parsed_time.microsecond,
    )
    return _datetime_to_matlab_datenum(dt)


def _time_to_day_fraction(value: str) -> float:
    try:
        parsed = datetime.strptime(f"{value}0", "%H:%M:%S.%f")
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%H:%M:%S")
        except ValueError:
            return np.nan
    return (
        parsed.hour * 3600.0 + parsed.minute * 60.0 + parsed.second + parsed.microsecond / 1e6
    ) / 86400.0


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return np.nan


def _value_key(value: Any) -> str:
    if isinstance(value, float) and np.isnan(value):
        return "__nan__"
    return repr(value)


def _to_scalar(value: Any) -> np.ndarray:
    if isinstance(value, str):
        return np.asarray(value)
    if isinstance(value, (float, int, np.number)):
        return np.asarray(value, dtype=float)
    return np.asarray(value)


def _sanitize_header_token(value: str) -> str:
    return "".join(ch if ord(ch) <= 127 else " " for ch in value).strip()


def _apply_qc(dataset: IMOSDataset, entries: list[_FieldMapEntry]) -> None:
    context: dict[str, Any] = {}
    for name in dataset.dataset.coords:
        context[str(name)] = dataset.dataset.coords[name].values
    for name in dataset.dataset.data_vars:
        context[str(name)] = dataset.dataset[name].values

    for entry in entries:
        if not entry.qc_expression:
            continue
        if entry.name not in dataset.dataset and entry.name not in dataset.dataset.coords:
            continue

        qc = _evaluate_qc(entry.qc_expression, context)
        if entry.name in dataset.dataset.data_vars:
            target = dataset.dataset[entry.name]
            qc_arr = _reshape_qc(qc, target.shape)
            dataset.dataset[f"{entry.name}_QC"] = (
                target.dims,
                np.asarray(qc_arr, dtype=np.int8),
            )
        else:
            target = dataset.dataset.coords[entry.name]
            qc_arr = _reshape_qc(qc, target.shape)
            dataset.dataset[f"{entry.name}_QC"] = (
                target.dims,
                np.asarray(qc_arr, dtype=np.int8),
            )


def _evaluate_qc(expression: str, context: dict[str, Any]) -> np.ndarray:
    expr = expression.strip()
    expr = re.sub(
        r"ones\s*\(\s*size\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\)",
        r"np.ones(np.shape(\1))",
        expr,
    )
    expr = re.sub(
        r"zeros\s*\(\s*size\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\)",
        r"np.zeros(np.shape(\1))",
        expr,
    )
    return np.asarray(eval(expr, {"np": np, "__builtins__": {}}, context))


def _reshape_qc(qc: np.ndarray, target_shape: tuple[int, ...]) -> np.ndarray:
    if target_shape == ():
        return np.asarray(qc).reshape(())
    if qc.shape == target_shape:
        return qc
    if qc.size == int(np.prod(target_shape)):
        return qc.reshape(target_shape)
    raise ValueError(f"QC shape mismatch: got {qc.shape}, expected {target_shape}")

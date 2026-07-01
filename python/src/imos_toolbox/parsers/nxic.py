"""FSI NXIC CTD binary parser.

Port of MATLAB `Parser/NXICBinaryParse.m`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser

_HEADER_LENGTH = 220
_MATLAB_EPOCH_1970 = 719529.0
_COORDS = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
_PRES_REL_APPLIED_OFFSET = -10.1325
_SAMPLE_LENGTH_CANDIDATES = np.asarray([37, 38, 39, 40, 41, 42], dtype=np.int32)


@dataclass
class _NXICHeader:
    instrument_make: str
    instrument_model: str
    instrument_serial_no: str
    sample_rate_hz: int
    average_seconds: float
    interval_seconds: float
    record_seconds: float
    sample_length: int
    interval_override: bool
    analog_dtype: str
    analog_scale: float
    sample_length_from_header: int | None = None


@dataclass
class _NXICSamples:
    time: np.ndarray
    conductivity: np.ndarray
    temperature: np.ndarray
    pressure: np.ndarray
    salinity: np.ndarray
    sound_speed: np.ndarray
    voltage: np.ndarray
    analog1: np.ndarray
    analog2: np.ndarray
    analog3: np.ndarray
    analog4: np.ndarray
    digital: np.ndarray | None


class NXICParser(BaseParser):
    """Parser for FSI NXIC CTD binary files (.ctd)."""

    parser_name = "NXIC"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("NXIC parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".ctd":
            raise ValueError("NXIC parser supports .ctd files only")

        raw = np.fromfile(source_file, dtype=np.uint8)
        if raw.size <= _HEADER_LENGTH:
            raise ValueError(f"NXIC file too short or empty: {source_file}")

        header = _parse_header(raw[:_HEADER_LENGTH], source_file)
        sample_bytes = raw[_HEADER_LENGTH:]
        header = _check_sample_length(sample_bytes, header)
        samples = _parse_samples(sample_bytes, header)

        dataset = IMOSDataset.empty()
        dataset.add_dimension("TIME", np.asarray(samples.time, dtype=float))

        dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
        dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
        dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])

        dataset.add_variable(
            "TEMP",
            data=np.asarray(samples.temperature, dtype=float),
            dims=["TIME"],
            attrs={"coordinates": _COORDS},
        )
        dataset.add_variable(
            "CNDC",
            data=np.asarray(samples.conductivity, dtype=float),
            dims=["TIME"],
            attrs={"coordinates": _COORDS},
        )
        dataset.add_variable(
            "PRES_REL",
            data=np.asarray(samples.pressure, dtype=float),
            dims=["TIME"],
            attrs={
                "coordinates": _COORDS,
                "applied_offset": np.float32(_PRES_REL_APPLIED_OFFSET),
            },
        )
        dataset.add_variable(
            "PSAL",
            data=np.asarray(samples.salinity, dtype=float),
            dims=["TIME"],
            attrs={"coordinates": _COORDS},
        )
        dataset.add_variable(
            "SSPD",
            data=np.asarray(samples.sound_speed, dtype=float),
            dims=["TIME"],
            attrs={"coordinates": _COORDS},
        )
        dataset.add_variable(
            "BAT_VOLT",
            data=np.asarray(samples.voltage, dtype=float),
            dims=["TIME"],
            attrs={"coordinates": _COORDS},
        )

        attrs: dict[str, str | float | int] = {
            "toolbox_input_file": str(source_file),
            "featureType": mode,
            "instrument_make": header.instrument_make,
            "instrument_model": header.instrument_model,
            "instrument_serial_no": header.instrument_serial_no,
            "parser": self.parser_name,
            "source_format": "ctd",
        }

        # Add calibration coefficients from header as metadata
        # (mirrors MATLAB header.Calibration struct — stored but not used for conversion)
        cal_attrs = _extract_calibration_metadata(raw[:_HEADER_LENGTH])
        attrs.update(cal_attrs)

        sample_interval, burst_interval, burst_duration = _burst_metadata(samples.time)
        if np.isfinite(sample_interval):
            attrs["instrument_sample_interval"] = int(round(sample_interval))
        if np.isfinite(burst_interval):
            attrs["instrument_burst_interval"] = int(round(burst_interval))
        if np.isfinite(burst_duration):
            attrs["instrument_burst_duration"] = int(round(burst_duration))

        dataset.set_attrs(attrs)
        return dataset


def _parse_header(header_bytes: np.ndarray, source_file: Path) -> _NXICHeader:
    serial = int(np.frombuffer(header_bytes[2:4].tobytes(), dtype="<u2")[0])

    if serial < 2276:
        instrument_make = "Falmouth Scientific Instruments"
        instrument_model = "NXIC CTD"
    else:
        instrument_make = "Teledyne"
        instrument_model = "Citadel CTD"

    options_interval = f"{int(header_bytes[5]):08b}"
    interval_operation = options_interval[7] == "1"

    if interval_operation:
        interval_seconds = float(
            int(header_bytes[28]) * 3600
            + int(header_bytes[29]) * 60
            + int(header_bytes[30])
        )
        record_seconds = float(
            int(header_bytes[31]) * 3600
            + int(header_bytes[32]) * 60
            + int(header_bytes[33])
        )
    else:
        interval_seconds = 0.0
        record_seconds = float("inf")

    average_seconds = float(int(header_bytes[26]) * 60 + int(header_bytes[27]))
    sample_rate_hz = int(np.frombuffer(header_bytes[9:11].tobytes(), dtype="<u2")[0])

    checksum = (int(np.sum(header_bytes[:154])) & 255) == int(header_bytes[154])
    if not checksum:
        raise ValueError(f"{source_file} header checksum failed")

    options_analog = f"{int(header_bytes[177]):08b}"
    range_bits = options_analog[6:8]
    if range_bits == "00":
        analog_dtype = "<i2"
        analog_scale = 5.0 / float(2**15)
    elif range_bits == "10":
        analog_dtype = "<u2"
        analog_scale = 5.0 / float(2**16)
    elif range_bits == "01":
        analog_dtype = "<i2"
        analog_scale = 10.0 / float(2**15)
    else:
        analog_dtype = "<u2"
        analog_scale = 10.0 / float(2**16)

    return _NXICHeader(
        instrument_make=instrument_make,
        instrument_model=instrument_model,
        instrument_serial_no=str(serial),
        sample_rate_hz=sample_rate_hz,
        average_seconds=average_seconds,
        interval_seconds=interval_seconds,
        record_seconds=record_seconds,
        sample_length=int(header_bytes[199]),
        interval_override=False,
        analog_dtype=analog_dtype,
        analog_scale=analog_scale,
    )


def _check_sample_length(sample_bytes: np.ndarray, header: _NXICHeader) -> _NXICHeader:
    dtest = np.full(_SAMPLE_LENGTH_CANDIDATES.shape, np.nan, dtype=np.float64)

    for i, sample_length in enumerate(_SAMPLE_LENGTH_CANDIDATES):
        test_logic: np.ndarray = np.zeros(int(sample_length) + 1, dtype=bool)
        test_logic[:: int(sample_length)] = True
        test_t = _index_to_time(sample_bytes, test_logic)
        if test_t.size > 1:
            dtest[i] = test_t[1] - test_t[0]

    raw_dtest = dtest.copy()
    dtest[dtest < 0] = np.inf
    dtest[dtest > 10.0 * header.interval_seconds] = np.inf

    finite = np.isfinite(dtest)
    if np.any(finite):
        i_min = int(np.argmin(dtest))
        candidate = int(_SAMPLE_LENGTH_CANDIDATES[i_min])
        if dtest[i_min] <= header.interval_seconds and candidate != header.sample_length:
            header.sample_length_from_header = header.sample_length
            header.sample_length = candidate
        return header

    # Continuous-mode fallback (interval can be 0 in header).
    if header.interval_seconds <= 0:
        valid = np.where(np.isfinite(raw_dtest) & (raw_dtest > 0))[0]
        if valid.size > 0:
            i_best = int(valid[np.argmin(raw_dtest[valid])])
            candidate = int(_SAMPLE_LENGTH_CANDIDATES[i_best])
            if candidate != header.sample_length:
                header.sample_length_from_header = header.sample_length
                header.sample_length = candidate

    return header


def _parse_samples(sample_bytes: np.ndarray, header: _NXICHeader) -> _NXICSamples:
    sample_length = int(header.sample_length)
    if sample_length < 37:
        raise ValueError(f"Invalid NXIC sample length: {sample_length}")

    record_bytes = sample_bytes.size
    if record_bytes < sample_length:
        raise ValueError("NXIC file contains no complete samples")

    time_logic: np.ndarray = np.zeros(record_bytes, dtype=bool)
    time_logic[::sample_length] = True
    times = _index_to_time(sample_bytes, time_logic)
    if times.size < 2:
        raise ValueError("Unable to decode NXIC timestamps")

    dt = np.diff(times)
    sample_interval, _, _ = _get_sample_interval_info(times)
    if (not header.interval_override) and sample_interval > 0:
        interval = sample_interval
    else:
        interval = header.interval_seconds
    if not np.isfinite(interval) or interval <= 0:
        positive_dt = dt[(dt > 0) & np.isfinite(dt)]
        interval = float(np.median(positive_dt)) if positive_dt.size > 0 else 1.0

    tberror = np.abs(dt) > interval * 2.0
    block_length = 5000 * sample_length
    block_overlap = 2 * sample_length

    iterations = 0
    while np.any(tberror):
        iterations += 1
        if iterations > 250:
            break

        ibad = int(np.flatnonzero(tberror)[0])
        tbad = float(times[ibad])
        starts = np.flatnonzero(time_logic)
        if ibad >= starts.size:
            break

        blockstart = int(starts[ibad])
        foundstart = False
        end_of_block = False

        while not end_of_block:
            blockend = blockstart + block_length + block_overlap
            if blockend > record_bytes - 4:
                blockend = record_bytes - 4
                end_of_block = True

            block_index: np.ndarray = np.arange(blockstart, blockend + 1, dtype=np.int64)
            reftimes = _index_to_time(sample_bytes, block_index)
            istart = np.flatnonzero(reftimes == tbad)

            if istart.size > 1:
                i_min = int(istart.min())
                i_max = int(istart.max())
                time_logic[blockstart + i_min + 1 :] = False
                time_logic[blockstart + i_max :: sample_length] = True
            elif istart.size == 1:
                i0 = int(istart[0])
                time_logic[blockstart + i0 + 1 :] = False
                if foundstart:
                    time_logic[blockstart + i0 :: sample_length] = True
                else:
                    foundstart = True

            if not end_of_block:
                blockstart = max(0, blockend - block_overlap)

        times = _index_to_time(sample_bytes, time_logic)
        dt = np.diff(times)
        tberror = np.abs(dt) > interval * 2.0

    starts = np.flatnonzero(time_logic)
    times = _index_to_time(sample_bytes, starts)

    order = np.argsort(times)
    sorted_times = times[order]
    starts = starts[order]

    _, reverse_unique_idx = np.unique(sorted_times[::-1], return_index=True)
    keep = np.sort(sorted_times.size - 1 - reverse_unique_idx)
    starts = starts[keep]

    starts = starts[starts + sample_length <= record_bytes]
    if starts.size == 0:
        raise ValueError("No complete NXIC samples found after realignment")

    data = np.zeros((sample_length, starts.size), dtype=np.uint8)
    for i in range(sample_length):
        data[i, :] = sample_bytes[starts + i]

    seconds: np.ndarray = _decode_u32(data[0:4, :]).astype(np.float64)
    hundredths = data[4, :].astype(np.float64) / 100.0
    matlab_time = _MATLAB_EPOCH_1970 + (seconds + hundredths) / 86400.0

    conductivity = _decode_f32(data[5:9, :]).astype(np.float64) / 10.0
    temperature: np.ndarray = _decode_f32(data[9:13, :]).astype(np.float64)
    pressure: np.ndarray = _decode_f32(data[13:17, :]).astype(np.float64)
    salinity: np.ndarray = _decode_f32(data[17:21, :]).astype(np.float64)
    sound_speed: np.ndarray = _decode_f32(data[21:25, :]).astype(np.float64)
    voltage: np.ndarray = _decode_f32(data[25:29, :]).astype(np.float64)

    analog1: np.ndarray = _decode_analog(data[29:31, :], header).astype(np.float64)
    analog2: np.ndarray = _decode_analog(data[31:33, :], header).astype(np.float64)
    analog3: np.ndarray = _decode_analog(data[33:35, :], header).astype(np.float64)
    analog4: np.ndarray = _decode_analog(data[35:37, :], header).astype(np.float64)

    digital: np.ndarray | None = None
    if sample_length >= 41:
        digital = _decode_f32(data[37:41, :]).astype(np.float64)

    return _NXICSamples(
        time=matlab_time,
        conductivity=conductivity,
        temperature=temperature,
        pressure=pressure,
        salinity=salinity,
        sound_speed=sound_speed,
        voltage=voltage,
        analog1=analog1,
        analog2=analog2,
        analog3=analog3,
        analog4=analog4,
        digital=digital,
    )


def _index_to_time(sample_bytes: np.ndarray, index: np.ndarray) -> np.ndarray:
    max_start = sample_bytes.size - 5
    if max_start < 0:
        return np.asarray([], dtype=np.float64)

    if index.dtype == bool:
        if index.size > max_start + 1:
            index = index[: max_start + 1]
        starts = np.flatnonzero(index)
    else:
        starts = index.astype(np.int64, copy=False)
        starts = starts[starts <= max_start]

    if starts.size == 0:
        return np.asarray([], dtype=np.float64)

    block = sample_bytes[starts[:, None] + np.arange(5, dtype=np.int64)]
    seconds = (
        block[:, 0].astype(np.uint32)
        | (block[:, 1].astype(np.uint32) << 8)
        | (block[:, 2].astype(np.uint32) << 16)
        | (block[:, 3].astype(np.uint32) << 24)
    ).astype(np.float64)
    return seconds + block[:, 4].astype(np.float64) / 100.0


def _get_sample_interval_info(time_values: np.ndarray) -> tuple[float, float, float]:
    if time_values.size < 3:
        return -1.0, -1.0, -1.0

    n10 = int(np.floor(time_values.size / 10.0 + 0.5))
    n10 = max(2, n10)
    dt = np.diff(time_values[:n10])
    if dt.size == 0:
        return -1.0, -1.0, -1.0

    dts = np.sort(dt)
    mask = np.concatenate([np.diff(dts) > 0, [True]])
    dts = dts[mask]

    if dts.size > 50:
        return -1.0, -1.0, -1.0

    mid = float(np.mean(dts))
    burst_interval_candidates = dt[dt < mid]
    record_interval_candidates = dt[dt > mid]

    if burst_interval_candidates.size == 0 or record_interval_candidates.size == 0:
        median_dt = float(np.median(dt))
        if np.isfinite(median_dt) and median_dt > 0:
            return median_dt, median_dt, 1.0
        return -1.0, -1.0, -1.0

    burst_interval = float(np.median(burst_interval_candidates))
    record_interval = float(np.median(record_interval_candidates))

    above_mid = np.flatnonzero(dt > mid)
    if above_mid.size > 1:
        nburst = float(np.median(np.diff(above_mid)))
    else:
        nburst = 1.0

    sample_interval = record_interval + burst_interval * (nburst - 1.0)
    return sample_interval, burst_interval, nburst


def _decode_u32(block: np.ndarray) -> np.ndarray:
    return np.frombuffer(np.ascontiguousarray(block.T).tobytes(), dtype="<u4")


def _decode_f32(block: np.ndarray) -> np.ndarray:
    return np.frombuffer(np.ascontiguousarray(block.T).tobytes(), dtype="<f4")


def _decode_analog(block: np.ndarray, header: _NXICHeader) -> np.ndarray:
    values = np.frombuffer(np.ascontiguousarray(block.T).tobytes(), dtype=header.analog_dtype)
    return values.astype(np.float64) * header.analog_scale


def _burst_metadata(time_values: np.ndarray) -> tuple[float, float, float]:
    if time_values.size < 2:
        return float("nan"), float("nan"), float("nan")

    dt = np.diff(time_values, prepend=time_values[0])
    burst_breaks = np.flatnonzero(dt > (1.0 / (24.0 * 60.0)))
    burst_edges = np.concatenate([[0], burst_breaks, [time_values.size]])

    sample_intervals: list[float] = []
    first_times: list[float] = []
    durations: list[float] = []

    for i in range(burst_edges.size - 1):
        burst_time = time_values[burst_edges[i] : burst_edges[i + 1]]
        if burst_time.size > 1:
            sample_interval = float(np.median(np.diff(burst_time) * 24.0 * 3600.0))
            sample_intervals.append(sample_interval)
            first_times.append(float(burst_time[0]))
            durations.append(
                float((burst_time[-1] - burst_time[0]) * 24.0 * 3600.0 + sample_interval)
            )

    if not sample_intervals:
        return float("nan"), float("nan"), float("nan")

    sample_interval = float(np.median(np.asarray(sample_intervals, dtype=float)))
    burst_interval = float("nan")
    if len(first_times) > 1:
        burst_interval = float(
            np.median(np.diff(np.asarray(first_times, dtype=float)) * 24.0 * 3600.0)
        )
    burst_duration = float(np.median(np.asarray(durations, dtype=float)))

    return sample_interval, burst_interval, burst_duration


def _extract_calibration_metadata(header_bytes: np.ndarray) -> dict[str, float]:
    """Extract calibration coefficients from NXIC header.

    Mirrors MATLAB NXICBinaryParse header.Calibration struct.
    These are stored as metadata only — the NXIC instrument applies
    calibration internally and outputs engineering units.

    Header byte offsets (all float32 LE):
      Conductivity: A1(55-58), B1(59-62), C1(63-66), D1(67-70)
      Temperature:  A2(71-74), B2(75-78), C2(79-82), D2(83-86)
      Pressure:     PA(87-90), PB(91-94)
    """
    cal: dict[str, float] = {}
    
    def _f32(offset: int) -> float:
        if offset + 4 <= len(header_bytes):
            return float(np.frombuffer(header_bytes[offset:offset + 4].tobytes(), dtype="<f4")[0])
        return float("nan")
    
    cal["calibration_cond_A1"] = _f32(54)
    cal["calibration_cond_B1"] = _f32(58)
    cal["calibration_cond_C1"] = _f32(62)
    cal["calibration_cond_D1"] = _f32(66)
    cal["calibration_temp_A2"] = _f32(70)
    cal["calibration_temp_B2"] = _f32(74)
    cal["calibration_temp_C2"] = _f32(78)
    cal["calibration_temp_D2"] = _f32(82)
    cal["calibration_pres_PA"] = _f32(86)
    cal["calibration_pres_PB"] = _f32(90)
    
    return cal

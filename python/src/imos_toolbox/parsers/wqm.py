"""WQM parser implementation (initial .dat and .raw support)."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser

_FIELD_MAP = {
    "COND(MMHO)": "CNDC",
    "COND(S/M)": "CNDC",
    "TEMP(C)": "TEMP",
    "PRES(DBAR)": "PRES_REL",
    "SAL(PSU)": "PSAL",
    "DO(MG/L)": "DOXY",
    "DO(MMOL/M^3)": "DOX1",
    "DO(ML/L)": "DOX",
    "CHL(UG/L)": "CPHL",
    "CHLA(UG/L)": "CPHL",
    "F-CAL-CHL(UG/L)": "CPHL",
    "FACT-CHL(UG/L)": "CPHL",
    "U-CAL-CHL(UG/L)": "CPHL",
    "RAWCHL(COUNTS)": "FLU2",
    "CHLA(COUNTS)": "FLU2",
    "NTU": "TURB",
    "NTU(NTU)": "TURB",
    "TURBIDITY(NTU)": "TURB",
    "RHO": "DENS",
    "PAR(UMOL_PHTN/M2/S)": "PAR",
}


class WQMParser(BaseParser):
    """Parser for Wetlabs WQM files."""

    parser_name = "WQM"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("WQM parser currently expects exactly one input file")

        source_file = file_list[0]
        suffix = source_file.suffix.lower()

        if suffix == ".dat":
            return _parse_dat(source_file, mode, self.parser_name)
        if suffix == ".raw":
            return _parse_raw(source_file, mode, self.parser_name)

        raise ValueError("WQM parser currently supports .dat and .raw files")


def _parse_dat(source_file: Path, mode: str, parser_name: str) -> IMOSDataset:
    lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    header_fields = _find_dat_header(lines)
    if not header_fields:
        raise ValueError(f"No valid WQM DAT header found in {source_file}")

    header_idx = next(idx for idx, line in enumerate(lines) if _looks_like_dat_header(line))

    field_index = {name.upper(): idx for idx, name in enumerate(header_fields)}
    date_idx = _first_existing_index(field_index, ["MMDDYY", "MM/DD/YY"])
    time_idx = _first_existing_index(field_index, ["HHMMSS", "HH:MM:SS"])
    serial_idx = _first_existing_index(field_index, ["WQM-SN", "SN"])
    if date_idx is None or time_idx is None:
        raise ValueError(f"WQM DAT missing date/time columns in {source_file}")

    by_var: dict[str, list[float]] = {}
    times: list[float] = []
    serial: str | None = None

    delimiter = "\t" if "\t" in lines[header_idx] else ","
    reader = csv.reader(lines[header_idx + 1 :], delimiter=delimiter)
    for row in reader:
        if len(row) < len(header_fields):
            continue

        try:
            dt = _parse_wqm_datetime(row[date_idx].strip(), row[time_idx].strip())
        except ValueError:
            continue

        times.append(_datetime_to_matlab_datenum(dt))

        if serial is None and serial_idx is not None:
            serial = row[serial_idx].strip()

        for idx, field in enumerate(header_fields):
            mapped = _map_field(field)
            if mapped is None:
                continue
            try:
                value = float(row[idx])
            except ValueError:
                value = np.nan
            by_var.setdefault(mapped, []).append(value)

    if not times:
        raise ValueError(f"No valid WQM DAT samples found in {source_file}")

    return _build_wqm_dataset(
        source_file=source_file,
        mode=mode,
        parser_name=parser_name,
        source_format="dat",
        times=times,
        values_by_var=by_var,
        serial=serial,
    )


def _parse_raw(source_file: Path, mode: str, parser_name: str) -> IMOSDataset:
    lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    header_lines = []
    payload_lines = []
    in_data = False
    for line in lines:
        stripped = line.strip()
        if stripped == "<EOH>":
            in_data = True
            continue
        if not in_data:
            header_lines.append(stripped)
        elif stripped:
            payload_lines.append(stripped)

    format_line = next((line for line in header_lines if line.upper().startswith("FILE FORMAT:")), "")
    payload_fields = _parse_raw_payload_fields(format_line)

    times: list[float] = []
    by_var: dict[str, list[float]] = {}
    serial: str | None = None

    for line in payload_lines:
        parts = [part.strip() for part in line.split(",", 4)]
        if len(parts) != 5:
            continue
        if parts[1] != "6":
            continue

        serial = serial or parts[0]
        try:
            dt = _parse_wqm_raw_datetime(parts[2], parts[3])
        except ValueError:
            continue

        payload_values = [token.strip() for token in parts[4].split(",")]
        if not payload_values:
            continue

        times.append(_datetime_to_matlab_datenum(dt))
        for idx, field in enumerate(payload_fields):
            if idx >= len(payload_values):
                continue
            mapped = _map_field(field)
            if mapped is None:
                continue
            try:
                value = float(payload_values[idx])
            except ValueError:
                value = np.nan
            by_var.setdefault(mapped, []).append(value)

    if not times:
        raise ValueError(f"No valid WQM RAW samples found in {source_file}")

    # Apply calibrations that MATLAB readWQMraw computes from header coefficients.
    # 1. Salinity from conductivity ratio (gsw_SP_from_R equivalent)
    # 2. O2 calibration (SBE-43F)
    # 3. CHL calibration (FLNTUcal: scale * (counts - offset))
    # 4. NTU calibration (FLNTUcal: scale * (counts - offset))
    # 5. PAR calibration (Im * 10^((freq - a0) / a1))
    _apply_raw_calibrations(header_lines, by_var)

    return _build_wqm_dataset(
        source_file=source_file,
        mode=mode,
        parser_name=parser_name,
        source_format="raw",
        times=times,
        values_by_var=by_var,
        serial=serial,
    )


def _build_wqm_dataset(
    source_file: Path,
    mode: str,
    parser_name: str,
    source_format: str,
    times: list[float],
    values_by_var: dict[str, list[float]],
    serial: str | None,
) -> IMOSDataset:
    """Build IMOS-compliant dataset from parsed WQM data.
    
    Mirrors MATLAB readWQMdat/readWQMraw variable assembly including:
    - TIME as dimension (not variable)
    - Scaffold variables (TIMESERIES, LATITUDE, LONGITUDE, NOMINAL_DEPTH)
    - coordinates attribute on all data variables
    - applied_offset on PRES_REL
    - CPHL numbering (CPHL, CPHL_2, CPHL_3...) for multiple CHL columns
    - Burst detection (instrument_burst_interval, burst_duration)
    """
    time_arr = np.asarray(times, dtype=float)
    dataset = IMOSDataset.empty()
    dataset.add_dimension("TIME", time_arr)
    
    # Scaffold variables (mirrors MATLAB)
    dataset.add_variable("TIMESERIES", data=np.int32(1), dims=[])
    dataset.add_variable("LATITUDE", data=np.float64(np.nan), dims=[])
    dataset.add_variable("LONGITUDE", data=np.float64(np.nan), dims=[])
    dataset.add_variable("NOMINAL_DEPTH", data=np.float32(np.nan), dims=[])
    
    coords = "TIME LATITUDE LONGITUDE NOMINAL_DEPTH"
    
    # CPHL numbering: if multiple CPHL columns, number them CPHL, CPHL_2, CPHL_3...
    # Mirrors MATLAB resolveIMOSName logic
    cphl_count = 0
    existing_names: set[str] = set()
    
    for var_name, values in values_by_var.items():
        if len(values) < len(times):
            values = [*values, *([np.nan] * (len(times) - len(values)))]
        
        # Resolve duplicate names (especially CPHL)
        resolved_name = var_name
        if var_name == "CPHL":
            cphl_count += 1
            if cphl_count > 1:
                resolved_name = f"CPHL_{cphl_count}"
        elif var_name in existing_names:
            suffix = 2
            while f"{var_name}_{suffix}" in existing_names:
                suffix += 1
            resolved_name = f"{var_name}_{suffix}"
        
        existing_names.add(resolved_name)
        
        var_attrs: dict = {"coordinates": coords}
        
        # applied_offset for PRES_REL (mirrors MATLAB: -14.7*0.689476)
        if resolved_name.startswith("PRES_REL"):
            var_attrs["applied_offset"] = np.float32(-14.7 * 0.689476)
        
        dataset.add_variable(
            name=resolved_name,
            data=np.asarray(values[: len(times)], dtype=float),
            dims=["TIME"],
            attrs=var_attrs,
        )
    
    # Burst detection (mirrors MATLAB readWQMdat burst logic)
    # dt > 1 minute (1/24/60 days) indicates burst boundary
    burst_interval = float("nan")
    burst_duration = float("nan")
    sample_interval = float("nan")
    if len(time_arr) > 1:
        dt = np.diff(time_arr)
        threshold = 1.0 / (24.0 * 60.0)  # 1 minute in days
        burst_starts = np.where(dt > threshold)[0] + 1
        burst_starts = np.concatenate([[0], burst_starts, [len(time_arr)]])
        
        n_bursts = len(burst_starts) - 1
        if n_bursts >= 1:
            intervals_in_burst = []
            first_times = []
            durations = []
            for i in range(n_bursts):
                burst_time = time_arr[burst_starts[i]:burst_starts[i + 1]]
                if len(burst_time) > 1:
                    si = float(np.median(np.diff(burst_time) * 24 * 3600))
                    intervals_in_burst.append(si)
                    first_times.append(burst_time[0])
                    durations.append(
                        (burst_time[-1] - burst_time[0]) * 24 * 3600 + si
                    )
            
            if intervals_in_burst:
                sample_interval = round(float(np.median(intervals_in_burst)))
            if len(first_times) > 1:
                burst_interval = round(
                    float(np.median(np.diff(np.array(first_times)) * 24 * 3600))
                )
            if durations:
                burst_duration = round(float(np.median(durations)))
    
    attrs: dict = {
        "toolbox_input_file": str(source_file),
        "featureType": mode,
        "instrument_make": "WET Labs",
        "instrument_model": "WQM",
        "instrument_sample_interval": sample_interval,
        "instrument_burst_interval": burst_interval,
        "instrument_burst_duration": burst_duration,
        "parser": parser_name,
        "source_format": source_format,
    }
    if serial:
        attrs["instrument_serial_no"] = serial
    dataset.set_attrs(attrs)
    return dataset


def _find_dat_header(lines: list[str]) -> list[str]:
    for line in lines:
        if _looks_like_dat_header(line):
            return [token.strip() for token in line.split("\t")]
    return []


def _looks_like_dat_header(line: str) -> bool:
    upper = line.upper()
    return ("MMDDYY" in upper or "MM/DD/YY" in upper) and ("HHMMSS" in upper or "HH:MM:SS" in upper)


def _first_existing_index(index_map: dict[str, int], names: list[str]) -> int | None:
    for name in names:
        if name in index_map:
            return index_map[name]
    return None


def _map_field(field_name: str) -> str | None:
    normalized = field_name.strip().upper()
    return _FIELD_MAP.get(normalized)


def _parse_raw_payload_fields(format_line: str) -> list[str]:
    if not format_line:
        return []
    _, _, right = format_line.partition(":")
    fields = [token.strip() for token in right.split(",")]
    # File format includes SN,State,Date,Time before payload; remove if present.
    payload_start = 0
    for idx, token in enumerate(fields):
        if token.upper().startswith("COND") or token.upper().startswith("TEMP"):
            payload_start = idx
            break
    return fields[payload_start:]


def _parse_wqm_datetime(date_text: str, time_text: str) -> datetime:
    for fmt in ("%m%d%y %H%M%S", "%m/%d/%y %H:%M:%S"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt)
        except ValueError:
            continue
    raise ValueError("Unsupported WQM DAT date/time format")


def _parse_wqm_raw_datetime(date_text: str, time_text: str) -> datetime:
    # RAW uses numeric date/time (MMDDYY, HHMMSS)
    return _parse_wqm_datetime(date_text, time_text)


def _datetime_to_matlab_datenum(value: datetime) -> float:
    ordinal = value.toordinal()
    frac = (value - datetime(value.year, value.month, value.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac


# ─── WQM RAW calibration functions (mirrors MATLAB readWQMraw.m) ───────────

def _apply_raw_calibrations(header_lines: list[str], by_var: dict[str, list[float]]) -> None:
    """Apply calibration to RAW sensor data in-place.
    
    Mirrors MATLAB readWQMraw: computes salinity from C/T/P via gsw,
    O2 from SBE-43F formula, CHL/NTU from scale+offset, PAR from log formula.
    """
    has_cond = "CNDC" in by_var
    has_temp = "TEMP" in by_var
    has_pres = "PRES_REL" in by_var
    
    # Salinity: gsw_SP_from_R(crat, T, P) where crat = 10*C / gsw_C3515
    # gsw_C3515 = 42.9140 mS/cm (conductivity of standard seawater)
    if has_cond and has_temp and has_pres:
        try:
            import gsw
            C = np.asarray(by_var["CNDC"])  # S/m
            T = np.asarray(by_var["TEMP"])  # °C
            P = np.asarray(by_var["PRES_REL"])  # dbar
            # MATLAB: crat = 10*WQM.conductivity./gsw_C3515
            # gsw_C3515 is in mS/cm = 42.914 → 10*C(S/m) converts S/m to mS/cm
            C_mScm = C * 10.0  # S/m → mS/cm
            crat = C_mScm / gsw.constants.C3515
            salinity = gsw.SP_from_R(crat, T, P)
            by_var["PSAL"] = salinity.tolist()
        except (ImportError, Exception):
            pass  # gsw not available or computation fails
    
    has_salinity = "PSAL" in by_var
    
    # O2 calibration (SBE-43F): only if we have salinity
    if has_salinity and has_temp and has_pres:
        o2_coefs = _load_oxygen_coefs(header_lines)
        # The DO field in raw is the raw frequency (Hz)
        # Find which key holds the raw DO — it could be mapped to DOX or DOXY
        raw_do_key = None
        for k in ("DOX", "DOXY", "DOX1"):
            if k in by_var:
                raw_do_key = k
                break
        if o2_coefs and raw_do_key:
            freq = np.asarray(by_var[raw_do_key])
            T = np.asarray(by_var["TEMP"])
            S = np.asarray(by_var["PSAL"])
            P = np.asarray(by_var["PRES_REL"])
            o2 = _o2cal(freq, o2_coefs, T, S, P)
            by_var[raw_do_key] = o2.tolist()
    
    # CHL calibration: FLNTUcal(counts, scale, offset)
    chl_coefs = _load_chl_coefs(header_lines)
    if chl_coefs:
        # FLU2 holds raw CHL counts; convert to CPHL engineering units
        if "FLU2" in by_var:
            counts = np.asarray(by_var["FLU2"])
            by_var["CPHL"] = _flntu_cal(counts, chl_coefs["scale"], chl_coefs["offset"]).tolist()
            # Keep FLU2 as raw counts too (MATLAB produces both U_Cal_CHL and fluorescence)
    
    # NTU calibration: FLNTUcal(counts, scale, offset)
    ntu_coefs = _load_ntu_coefs(header_lines)
    if ntu_coefs and "TURB" in by_var:
        counts = np.asarray(by_var["TURB"])
        by_var["TURB"] = _flntu_cal(counts, ntu_coefs["scale"], ntu_coefs["offset"]).tolist()
    
    # PAR calibration: Im * 10^((freq - a0) / a1)
    par_coefs = _load_par_coefs(header_lines)
    if par_coefs and "PAR" in by_var:
        freq = np.asarray(by_var["PAR"])
        by_var["PAR"] = _par_cal(freq, par_coefs["Im"], par_coefs["a0"], par_coefs["a1"]).tolist()


def _o2cal(freq: np.ndarray, coefs: dict, T: np.ndarray, S: np.ndarray, P: np.ndarray) -> np.ndarray:
    """SBE-43F oxygen calibration. Mirrors MATLAB O2cal function.
    
    O2 = Soc*(freq+FOffset) * (1+A*T+B*T²+C*T³) * OxSat(S,T) * exp(E*P/K)
    """
    Soc = coefs["Soc"]
    FOffset = coefs["FOffset"]
    A = coefs["A"]
    B = coefs["B"]
    C = coefs["C"]
    E = coefs["E"]
    
    P1 = Soc * (freq + FOffset)
    P2 = 1.0 + A * T + B * T**2 + C * T**3
    K = T + 273.15
    P3 = np.exp(E * P / K)
    oxsat = _sw_sat_o2(S, T)  # ml/l (Weiss saturation)
    
    O2 = P1 * P2 * oxsat * P3
    O2[freq == 30000] = np.nan  # bad flag
    return O2


def _sw_sat_o2(S: np.ndarray, T: np.ndarray) -> np.ndarray:
    """Oxygen saturation in ml/l (Weiss 1970 formula).
    
    Mirrors MATLAB sw_satO2 / Seawater toolbox.
    """
    # Weiss (1970) DSR 17:721-735 — oxygen solubility in ml/l
    T_abs = (T + 273.15) / 100.0
    oxsat = np.exp(
        -173.4292
        + 249.6339 / T_abs
        + 143.3483 * np.log(T_abs)
        - 21.8492 * T_abs
        + S * (-0.033096 + 0.014259 * T_abs - 0.0017000 * T_abs**2)
    )
    return oxsat


def _flntu_cal(counts: np.ndarray, scale: float, offset: float) -> np.ndarray:
    """FLNTUcal: scale * (counts - offset). Mirrors MATLAB FLNTUcal."""
    return scale * (counts - offset)


def _par_cal(freq: np.ndarray, Im: float, a0: float, a1: float) -> np.ndarray:
    """PARcal: Im * 10^((freq - a0) / a1). Mirrors MATLAB PARcal (log)."""
    return Im * np.power(10.0, (freq - a0) / a1)


def _load_oxygen_coefs(header_lines: list[str]) -> dict | None:
    """Extract O2 calibration coefficients from header.
    
    Mirrors MATLAB load_oxygen_coefs: tries 'Soc=', 'A52=' first,
    then 'IDO43 Soc=', 'IDO43 A=' for newer formats.
    """
    import re
    
    coef_map: dict[str, float] = {}
    patterns_old = {
        "Soc": r"Soc=\s*([\d.eE+-]+)",
        "FOffset": r"FOffset=\s*([\d.eE+-]+)",
        "A": r"A52=\s*([\d.eE+-]+)",
        "B": r"B52=\s*([\d.eE+-]+)",
        "C": r"C52=\s*([\d.eE+-]+)",
        "E": r"E52=\s*([\d.eE+-]+)",
    }
    patterns_new = {
        "Soc": r"IDO43 Soc=\s*([\d.eE+-]+)",
        "FOffset": r"IDO43 FOffset=\s*([\d.eE+-]+)",
        "A": r"IDO43 A=\s*([\d.eE+-]+)",
        "B": r"IDO43 B=\s*([\d.eE+-]+)",
        "C": r"IDO43 C=\s*([\d.eE+-]+)",
        "E": r"IDO43 E=\s*([\d.eE+-]+)",
    }
    
    for patterns in (patterns_old, patterns_new):
        coef_map = {}
        for coef_name, pattern in patterns.items():
            for line in header_lines:
                m = re.search(pattern, line)
                if m:
                    coef_map[coef_name] = float(m.group(1))
                    break
        if len(coef_map) == 6:
            return coef_map
    
    return None if len(coef_map) < 6 else coef_map


def _load_chl_coefs(header_lines: list[str]) -> dict | None:
    """Extract CHL calibration coefficients. Mirrors MATLAB load_chl."""
    import re
    
    # Try older format: UserCHL=scale offset
    for line in header_lines:
        m = re.match(r"UserCHL=\s*([\d.eE+-]+)\s+([\d.eE+-]+)", line)
        if m:
            return {"scale": float(m.group(1)), "offset": float(m.group(2))}
    
    # Try newer ECO Signal format
    for i, line in enumerate(header_lines):
        if re.search(r"ECO Signal \d+ Name:\s*CHLA", line, re.IGNORECASE):
            m = re.search(r"ECO Signal (\d+) Name:", line)
            if m:
                sig_num = m.group(1)
                cal_pattern = f"ECO Signal {sig_num} Cal Coef:"
                for cal_line in header_lines:
                    if cal_pattern in cal_line:
                        parts = cal_line.split(":", 1)[1].strip().split()
                        if len(parts) >= 2:
                            return {"scale": float(parts[0]), "offset": float(parts[1])}
    return None


def _load_ntu_coefs(header_lines: list[str]) -> dict | None:
    """Extract NTU calibration coefficients. Mirrors MATLAB load_ntu."""
    import re
    
    # Try older format: NTU=scale offset
    for line in header_lines:
        m = re.match(r"NTU=\s*([\d.eE+-]+)\s+([\d.eE+-]+)", line)
        if m:
            return {"scale": float(m.group(1)), "offset": float(m.group(2))}
    
    # Try newer ECO Signal format
    for line in header_lines:
        if re.search(r"ECO Signal \d+ Name:\s*TURBIDITY", line, re.IGNORECASE):
            m = re.search(r"ECO Signal (\d+) Name:", line)
            if m:
                sig_num = m.group(1)
                cal_pattern = f"ECO Signal {sig_num} Cal Coef:"
                for cal_line in header_lines:
                    if cal_pattern in cal_line:
                        parts = cal_line.split(":", 1)[1].strip().split()
                        if len(parts) >= 2:
                            return {"scale": float(parts[0]), "offset": float(parts[1])}
    return None


def _load_par_coefs(header_lines: list[str]) -> dict | None:
    """Extract PAR calibration coefficients. Mirrors MATLAB: PAR=Im a0 a1."""
    import re
    
    for line in header_lines:
        m = re.match(r"PAR=\s*([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)", line)
        if m:
            return {"Im": float(m.group(1)), "a0": float(m.group(2)), "a1": float(m.group(3))}
    return None

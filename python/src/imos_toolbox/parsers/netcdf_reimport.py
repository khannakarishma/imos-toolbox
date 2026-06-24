"""NetCDF re-import parser implementation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

from imos_toolbox.model import IMOSDataset, QC_SUFFIX
from imos_toolbox.parsers.base import BaseParser

# IMOS NetCDF files store time as days since 1950-01-01
# MATLAB datenum('1950-01-01 00:00:00') == 712224
IMOS_MATLAB_DATENUM_EPOCH = 712224


class NetCDFReimportParser(BaseParser):
    """Parser for re-importing IMOS-compliant NetCDF files."""

    parser_name = "netcdfParse"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("NetCDF re-import parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() not in {".nc", ".netcdf"}:
            raise ValueError("NetCDF re-import parser expects .nc or .netcdf files")

        # Load the NetCDF file with xarray
        ds = xr.open_dataset(source_file, decode_times=False)

        # Convert TIME dimension from IMOS epoch (days since 1950) to MATLAB datenum
        if "TIME" in ds.coords or "TIME" in ds.data_vars:
            time_var = ds["TIME"]
            # IMOS stores as days since 1950-01-01, MATLAB datenum is days since 0000-01-01
            # MATLAB datenum('1950-01-01 00:00:00') == 712224
            ds["TIME"] = time_var + IMOS_MATLAB_DATENUM_EPOCH

        # Wrap in IMOSDataset
        dataset = IMOSDataset.from_xarray(ds)

        # Preserve global attributes and add parser metadata
        attrs = dict(ds.attrs)
        attrs["toolbox_input_file"] = str(source_file)
        attrs["parser"] = self.parser_name
        attrs["source_format"] = "netcdf"

        # Update date_created to current time (as MATLAB version does)
        attrs["date_created"] = _now_utc_matlab_datenum()

        # Ensure featureType matches the requested mode
        if "featureType" not in attrs:
            attrs["featureType"] = mode

        dataset.set_attrs(attrs)

        return dataset


def _now_utc_matlab_datenum() -> float:
    """Return current UTC time as MATLAB datenum."""
    now = datetime.utcnow()
    ordinal = now.toordinal()
    frac = (now - datetime(now.year, now.month, now.day)).total_seconds() / 86400.0
    return ordinal + 366 + frac

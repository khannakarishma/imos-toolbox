#!/usr/bin/env python3
"""Verify SBE parser outputs against expected MATLAB structure.

This script runs each Family A parser on real test files and prints
the complete output structure for manual comparison against MATLAB.
"""
import sys
sys.path.insert(0, 'src')

import numpy as np
from pathlib import Path
from imos_toolbox.parsers.sbe19 import SBE19Parser
from imos_toolbox.parsers.sbe37 import SBE37Parser
from imos_toolbox.parsers.sbe39 import SBE39Parser

def print_dataset_summary(label: str, dataset):
    """Print a summary of the dataset matching MATLAB output structure."""
    ds = dataset.dataset
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    
    # Dimensions (mirrors MATLAB sample_data.dimensions)
    print(f"\n  DIMENSIONS:")
    for dim_name, dim_size in ds.dims.items():
        dim_data = ds.coords[dim_name].values if dim_name in ds.coords else None
        if dim_data is not None and len(dim_data) > 0:
            print(f"    {dim_name}: size={dim_size}, first={dim_data[0]:.6f}, last={dim_data[-1]:.6f}")
        else:
            print(f"    {dim_name}: size={dim_size}")
    
    # Variables (mirrors MATLAB sample_data.variables)
    print(f"\n  VARIABLES ({len(ds.data_vars)}):")
    for var_name in ds.data_vars:
        var = ds[var_name]
        dims_str = str(var.dims) if var.dims else "(scalar)"
        
        if var.dims:
            data = var.values
            non_nan = data[~np.isnan(data)] if np.issubdtype(data.dtype, np.floating) else data
            if len(non_nan) > 0:
                print(f"    {var_name}: dims={dims_str}, dtype={var.dtype}, "
                      f"shape={var.shape}, min={np.nanmin(data):.6f}, max={np.nanmax(data):.6f}")
            else:
                print(f"    {var_name}: dims={dims_str}, dtype={var.dtype}, shape={var.shape}, ALL NaN")
        else:
            print(f"    {var_name}: dims={dims_str}, dtype={var.dtype}, value={var.values}")
        
        # Attributes
        for attr_name, attr_val in var.attrs.items():
            print(f"      .{attr_name} = {repr(attr_val)[:80]}")
    
    # Global attributes (mirrors MATLAB sample_data.meta)
    print(f"\n  GLOBAL ATTRIBUTES:")
    for attr_name, attr_val in sorted(ds.attrs.items()):
        print(f"    {attr_name} = {repr(attr_val)[:80]}")
    
    print()


def verify_sbe19():
    """Test SBE19 with real .cnv file."""
    data_dir = Path("tests/parsers/data/sbe/sbe19")
    test_file = data_dir / "SBE19plus_parser1.cnv"
    if not test_file.exists():
        print(f"SKIP: {test_file} not found")
        return
    
    parser = SBE19Parser()
    dataset = parser.parse([str(test_file)], "timeSeries")
    print_dataset_summary(f"SBE19 — {test_file.name} (timeSeries)", dataset)


def verify_sbe37():
    """Test SBE37 with real .cnv file."""
    data_dir = Path("tests/parsers/data/sbe/sbe37")
    test_file = data_dir / "SBE37_parser1.cnv"
    if not test_file.exists():
        print(f"SKIP: {test_file} not found")
        return
    
    parser = SBE37Parser()
    dataset = parser.parse([str(test_file)], "timeSeries")
    print_dataset_summary(f"SBE37 — {test_file.name} (timeSeries)", dataset)


def verify_sbe39():
    """Test SBE39 with real .asc file."""
    data_dir = Path("tests/parsers/data/sbe/sbe39")
    files = sorted(data_dir.glob("*.asc"))
    if not files:
        print(f"SKIP: No .asc files in {data_dir}")
        return
    
    parser = SBE39Parser()
    dataset = parser.parse([str(files[0])], "timeSeries")
    print_dataset_summary(f"SBE39 — {files[0].name} (timeSeries)", dataset)


if __name__ == "__main__":
    verify_sbe19()
    verify_sbe37()
    verify_sbe39()

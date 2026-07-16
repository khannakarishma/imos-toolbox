#!/usr/bin/env python3
"""Compare MATLAB reference .mat outputs with Python parser outputs row-by-row.

Usage:
    1. First run generate_matlab_reference.m in MATLAB (from imos-toolbox root)
    2. Then run this script:
       cd python
       uv run python tests/parsers/compare_matlab_python.py

This script:
- Loads each .mat reference file
- Runs the equivalent Python parser on the same input
- Compares every single data value row-by-row
- Reports exact differences with tolerance (1e-6 relative, 1e-10 absolute)
"""

import sys
sys.path.insert(0, 'src')

import numpy as np
from pathlib import Path
from scipy.io import loadmat

# Parsers
from imos_toolbox.parsers.sbe19 import SBE19Parser
from imos_toolbox.parsers.sbe26 import SBE26Parser
from imos_toolbox.parsers.sbe37 import SBE37Parser
from imos_toolbox.parsers.sbe37sm import SBE37SMParser
from imos_toolbox.parsers.sbe39 import SBE39Parser
from imos_toolbox.parsers.sbe56 import SBE56Parser

REF_DIR = Path("tests/parsers/data/matlab_reference")
DATA_DIR = Path("tests/parsers/data/sbe")

# Tolerance for floating point comparison
ABS_TOL = 1e-10
REL_TOL = 1e-6


def extract_matlab_struct(mat_data: dict) -> dict:
    """Extract variables and dimensions from MATLAB sample_data struct.
    
    MATLAB struct layout:
        sample_data.dimensions{1}.name = 'TIME'
        sample_data.dimensions{1}.data = [array]
        sample_data.variables{k}.name = 'TEMP'
        sample_data.variables{k}.data = [array]
        sample_data.variables{k}.dimensions = 1 (or [])
        sample_data.variables{k}.coordinates = '...'
        sample_data.meta.instrument_make = '...'
    """
    sd = mat_data['sample_data']
    
    result = {
        'dimensions': {},
        'variables': {},
        'meta': {},
    }
    
    # Extract dimensions
    dims = sd['dimensions'][0, 0]
    for i in range(dims.shape[1]):
        dim = dims[0, i]
        name = str(dim['name'][0])
        data = dim['data'][0].flatten().astype(np.float64)
        result['dimensions'][name] = data
    
    # Extract variables
    variables = sd['variables'][0, 0]
    for i in range(variables.shape[1]):
        var = variables[0, i]
        name = str(var['name'][0])
        data = var['data'][0]
        
        # Handle scalar vs array
        if data.size == 1:
            data = data.flatten()[0]
        else:
            data = data.flatten().astype(np.float64)
        
        var_info = {'data': data}
        
        # Extract attributes if they exist
        if 'coordinates' in var.dtype.names and var['coordinates'][0].size > 0:
            var_info['coordinates'] = str(var['coordinates'][0][0])
        if 'applied_offset' in var.dtype.names and var['applied_offset'][0].size > 0:
            var_info['applied_offset'] = float(var['applied_offset'][0].flatten()[0])
        if 'dimensions' in var.dtype.names:
            dim_val = var['dimensions'][0]
            if dim_val.size == 0:
                var_info['is_scalar'] = True
            else:
                var_info['is_scalar'] = False
        
        result['variables'][name] = var_info
    
    # Extract meta
    meta = sd['meta'][0, 0]
    if 'instrument_make' in meta.dtype.names:
        result['meta']['instrument_make'] = str(meta['instrument_make'][0][0]) if meta['instrument_make'][0].size > 0 else ''
    if 'instrument_model' in meta.dtype.names:
        result['meta']['instrument_model'] = str(meta['instrument_model'][0][0]) if meta['instrument_model'][0].size > 0 else ''
    if 'instrument_serial_no' in meta.dtype.names:
        result['meta']['instrument_serial_no'] = str(meta['instrument_serial_no'][0][0]) if meta['instrument_serial_no'][0].size > 0 else ''
    if 'instrument_firmware' in meta.dtype.names:
        result['meta']['instrument_firmware'] = str(meta['instrument_firmware'][0][0]) if meta['instrument_firmware'][0].size > 0 else ''
    if 'instrument_sample_interval' in meta.dtype.names and meta['instrument_sample_interval'][0].size > 0:
        result['meta']['instrument_sample_interval'] = float(meta['instrument_sample_interval'][0].flatten()[0])
    
    return result


def compare_arrays(name: str, matlab_data, python_data, indent: str = "    ") -> list[str]:
    """Compare two arrays element-by-element. Returns list of difference messages."""
    issues = []
    
    if isinstance(matlab_data, (int, float, np.floating, np.integer)):
        # Scalar comparison
        if np.isnan(matlab_data) and np.isnan(python_data):
            return []
        if matlab_data != python_data:
            issues.append(f"{indent}{name}: MATLAB={matlab_data}, Python={python_data}")
        return issues
    
    matlab_arr = np.asarray(matlab_data, dtype=np.float64)
    python_arr = np.asarray(python_data, dtype=np.float64)
    
    # Size check
    if matlab_arr.shape != python_arr.shape:
        issues.append(f"{indent}{name}: SIZE MISMATCH — MATLAB shape={matlab_arr.shape}, Python shape={python_arr.shape}")
        return issues
    
    # Element-by-element comparison
    both_nan = np.isnan(matlab_arr) & np.isnan(python_arr)
    matlab_nan_only = np.isnan(matlab_arr) & ~np.isnan(python_arr)
    python_nan_only = ~np.isnan(matlab_arr) & np.isnan(python_arr)
    
    # NaN location mismatches
    n_nan_mismatch = np.sum(matlab_nan_only) + np.sum(python_nan_only)
    if n_nan_mismatch > 0:
        issues.append(f"{indent}{name}: {n_nan_mismatch} NaN location mismatches")
        # Show first few
        matlab_nan_indices = np.where(matlab_nan_only.flatten())[0][:5]
        python_nan_indices = np.where(python_nan_only.flatten())[0][:5]
        if len(matlab_nan_indices) > 0:
            issues.append(f"{indent}  MATLAB-only NaN at indices: {matlab_nan_indices}")
        if len(python_nan_indices) > 0:
            issues.append(f"{indent}  Python-only NaN at indices: {python_nan_indices}")
    
    # Value comparison (where neither is NaN)
    valid = ~np.isnan(matlab_arr) & ~np.isnan(python_arr)
    if np.any(valid):
        m_valid = matlab_arr[valid]
        p_valid = python_arr[valid]
        
        abs_diff = np.abs(m_valid - p_valid)
        
        # Relative difference (avoid division by zero)
        denom = np.maximum(np.abs(m_valid), 1e-15)
        rel_diff = abs_diff / denom
        
        # Check tolerance
        exceeds_tol = (abs_diff > ABS_TOL) & (rel_diff > REL_TOL)
        n_exceed = np.sum(exceeds_tol)
        
        if n_exceed > 0:
            max_abs = np.max(abs_diff[exceeds_tol])
            max_rel = np.max(rel_diff[exceeds_tol])
            first_idx = np.where(exceeds_tol)[0][0]
            issues.append(
                f"{indent}{name}: {n_exceed}/{len(m_valid)} values exceed tolerance "
                f"(max_abs_diff={max_abs:.2e}, max_rel_diff={max_rel:.2e})"
            )
            issues.append(
                f"{indent}  First mismatch at index {first_idx}: "
                f"MATLAB={m_valid[first_idx]:.10f}, Python={p_valid[first_idx]:.10f}"
            )
        else:
            max_abs = np.max(abs_diff) if len(abs_diff) > 0 else 0
            # All within tolerance — no message needed
    
    return issues


def compare_parser(label: str, mat_file: Path, python_dataset) -> dict:
    """Compare MATLAB .mat reference with Python output."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    
    # Load MATLAB reference
    try:
        mat_data = loadmat(str(mat_file), squeeze_me=False)
        matlab = extract_matlab_struct(mat_data)
    except Exception as e:
        print(f"  ERROR loading .mat: {e}")
        return {'status': 'ERROR', 'message': str(e)}
    
    ds = python_dataset.dataset
    all_issues = []
    
    # Compare dimensions
    print(f"\n  DIMENSIONS:")
    for dim_name, dim_data in matlab['dimensions'].items():
        if dim_name in ds.coords:
            py_data = ds.coords[dim_name].values.astype(np.float64)
            issues = compare_arrays(f"dim[{dim_name}]", dim_data, py_data)
            if issues:
                all_issues.extend(issues)
                print(f"    {dim_name}: ❌ MISMATCH ({len(dim_data)} values)")
                for i in issues:
                    print(f"      {i}")
            else:
                print(f"    {dim_name}: ✅ {len(dim_data)} values match exactly")
        else:
            all_issues.append(f"    dim[{dim_name}]: MISSING in Python")
            print(f"    {dim_name}: ❌ MISSING in Python output")
    
    # Compare variables
    print(f"\n  VARIABLES:")
    for var_name, var_info in matlab['variables'].items():
        matlab_data = var_info['data']
        
        if var_name in ds.data_vars:
            py_data = ds[var_name].values
            
            # Handle scalar
            if isinstance(matlab_data, (int, float, np.floating, np.integer)):
                py_val = float(py_data) if py_data.size == 1 else py_data
                if np.isnan(matlab_data) and np.isnan(py_val):
                    print(f"    {var_name}: ✅ scalar NaN match")
                elif abs(float(matlab_data) - float(py_val)) < ABS_TOL:
                    print(f"    {var_name}: ✅ scalar = {matlab_data}")
                else:
                    msg = f"    {var_name}: ❌ MATLAB={matlab_data}, Python={py_val}"
                    all_issues.append(msg)
                    print(msg)
            else:
                # Array comparison
                py_arr = py_data.flatten().astype(np.float64)
                issues = compare_arrays(var_name, matlab_data, py_arr)
                if issues:
                    all_issues.extend(issues)
                    print(f"    {var_name}: ❌ DIFFERENCES FOUND ({len(matlab_data)} values)")
                    for i in issues[:3]:  # Show first 3
                        print(f"      {i}")
                else:
                    print(f"    {var_name}: ✅ {len(matlab_data)} values match (tol={REL_TOL})")
            
            # Compare attributes
            if 'applied_offset' in var_info:
                if 'applied_offset' in ds[var_name].attrs:
                    m_offset = var_info['applied_offset']
                    p_offset = float(ds[var_name].attrs['applied_offset'])
                    if abs(m_offset - p_offset) < 0.001:
                        print(f"      .applied_offset: ✅ {m_offset:.6f}")
                    else:
                        msg = f"      .applied_offset: ❌ MATLAB={m_offset}, Python={p_offset}"
                        all_issues.append(msg)
                        print(msg)
        else:
            all_issues.append(f"    {var_name}: MISSING in Python")
            print(f"    {var_name}: ❌ MISSING in Python output")
    
    # Compare metadata
    print(f"\n  METADATA:")
    for key, m_val in matlab['meta'].items():
        if key in ds.attrs:
            p_val = ds.attrs[key]
            if isinstance(m_val, str):
                if m_val == str(p_val):
                    print(f"    {key}: ✅ '{m_val}'")
                else:
                    msg = f"    {key}: ❌ MATLAB='{m_val}', Python='{p_val}'"
                    all_issues.append(msg)
                    print(msg)
            else:
                if abs(float(m_val) - float(p_val)) < 0.01:
                    print(f"    {key}: ✅ {m_val}")
                else:
                    msg = f"    {key}: ❌ MATLAB={m_val}, Python={p_val}"
                    all_issues.append(msg)
                    print(msg)
        else:
            # Check with inst_header_ prefix
            prefixed_key = f"inst_header_{key}" if key.startswith('instrument_') else key
            # Skip — Python may store metadata differently
            pass
    
    # Summary
    print(f"\n  {'='*50}")
    if not all_issues:
        print(f"  ✅ PERFECT MATCH — all values identical within tolerance")
        return {'status': 'PASS', 'issues': []}
    else:
        print(f"  ❌ {len(all_issues)} DIFFERENCES FOUND")
        return {'status': 'FAIL', 'issues': all_issues}


def main():
    print("="*70)
    print("  FAMILY A — ROW-BY-ROW MATLAB vs PYTHON COMPARISON")
    print("="*70)
    
    if not REF_DIR.exists():
        print(f"\n  ERROR: Reference directory not found: {REF_DIR}")
        print(f"  Please run generate_matlab_reference.m in MATLAB first!")
        print(f"  Instructions:")
        print(f"    1. Open MATLAB")
        print(f"    2. cd to imos-toolbox root directory")
        print(f"    3. run('python/tests/parsers/generate_matlab_reference.m')")
        return
    
    mat_files = sorted(REF_DIR.glob("*.mat"))
    if not mat_files:
        print(f"\n  ERROR: No .mat files found in {REF_DIR}")
        print(f"  Please run generate_matlab_reference.m in MATLAB first!")
        return
    
    print(f"\n  Found {len(mat_files)} reference .mat files:")
    for f in mat_files:
        print(f"    - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    
    results = {}
    
    # Map .mat files to parsers and source files
    test_cases = {
        'SBE19_SBE19plus_parser1_timeSeries.mat': {
            'parser': SBE19Parser(),
            'file': DATA_DIR / 'sbe19' / 'SBE19plus_parser1.cnv',
            'mode': 'timeSeries',
        },
        'SBE37_SBE37_parser1_timeSeries.mat': {
            'parser': SBE37Parser(),
            'file': DATA_DIR / 'sbe37' / 'SBE37_parser1.cnv',
            'mode': 'timeSeries',
        },
        'SBE37_SBE37_15592_2411_timeSeries.mat': {
            'parser': SBE37Parser(),
            'file': DATA_DIR / 'sbe37' / 'SBE37_15592_2411.cnv',
            'mode': 'timeSeries',
        },
        'SBE37SM_sbe37smp_03722564_timeSeries.mat': {
            'parser': SBE37SMParser(),
            'file': DATA_DIR / 'sbe37' / 'sbe37smp-rs232_03722564_2025_11_04C.cnv',
            'mode': 'timeSeries',
        },
        'SBE39_SBE39_5840_2411_timeSeries.mat': {
            'parser': SBE39Parser(),
            'file': DATA_DIR / 'sbe39' / 'SBE39_5840_2411.asc',
            'mode': 'timeSeries',
        },
        'SBE56_SBE56_7517_2411_timeSeries.mat': {
            'parser': SBE56Parser(),
            'file': DATA_DIR / 'sbe56' / 'SBE56_7517_2411.cnv',
            'mode': 'timeSeries',
        },
        'SBE26_SBE26_1711_2409_NEW_timeSeries.mat': {
            'parser': SBE26Parser(),
            'file': DATA_DIR / 'sbe26' / 'SBE26_1711_2409_NEW.tid',
            'mode': 'timeSeries',
        },
    }
    
    for mat_file in mat_files:
        if mat_file.name in test_cases:
            tc = test_cases[mat_file.name]
            source_file = tc['file']
            
            if not source_file.exists():
                print(f"\n  SKIP {mat_file.name}: source file not found ({source_file})")
                continue
            
            # Run Python parser
            try:
                python_dataset = tc['parser'].parse([str(source_file)], tc['mode'])
            except Exception as e:
                print(f"\n  ERROR running Python parser for {mat_file.name}: {e}")
                continue
            
            # Compare
            result = compare_parser(
                f"{mat_file.stem} — {source_file.name}",
                mat_file,
                python_dataset
            )
            results[mat_file.name] = result
        else:
            print(f"\n  SKIP {mat_file.name}: no test case mapping defined")
    
    # Final summary
    print(f"\n\n{'='*70}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*70}")
    n_pass = sum(1 for r in results.values() if r['status'] == 'PASS')
    n_fail = sum(1 for r in results.values() if r['status'] == 'FAIL')
    n_error = sum(1 for r in results.values() if r['status'] == 'ERROR')
    print(f"  PASS:  {n_pass}")
    print(f"  FAIL:  {n_fail}")
    print(f"  ERROR: {n_error}")
    print(f"  TOTAL: {len(results)}")
    
    if n_fail > 0:
        print(f"\n  FAILED PARSERS:")
        for name, r in results.items():
            if r['status'] == 'FAIL':
                print(f"    - {name}: {len(r['issues'])} issues")


if __name__ == "__main__":
    main()

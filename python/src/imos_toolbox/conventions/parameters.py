"""Parameter registry loader."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from imos_toolbox.conventions._parser import coerce_value, parse_csv

FIELDS = [
    "name",
    "is_cf",
    "standard_name",
    "units",
    "direction_positive",
    "reference_datum",
    "data_code",
    "fill_value",
    "valid_min",
    "valid_max",
    "netcdf_type",
]


def load_parameters(path: str | Path) -> List[Dict[str, object]]:
    rows = parse_csv(path)
    parameters: List[Dict[str, object]] = []
    for row in rows:
        if not row:
            continue
        normalized = [field.replace("percent", "%") for field in row]
        values = [coerce_value(field) for field in normalized]
        entry = {key: values[idx] if idx < len(values) else "" for idx, key in enumerate(FIELDS)}
        parameters.append(entry)
    return parameters

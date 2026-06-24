"""Echoview CSV export parser.

Port of MATLAB echoviewParse.m.
Parses CSV exports from Echoview acoustic processing software.

MATLAB source: Parser/echoviewParse.m (777 lines)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser


class EchoviewParser(BaseParser):
    """Parser for Echoview CSV exports.
    
    Mirrors MATLAB echoviewParse.m. Reads CSV files exported from
    Echoview acoustic processing software containing backscatter data.
    """

    parser_name = "Echoview"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        """Parse Echoview CSV export.
        
        Args:
            filenames: List of file paths (only first used)
            mode: Toolbox mode
            
        Returns:
            IMOSDataset with acoustic backscatter data
            
        Raises:
            NotImplementedError: Full parsing not yet implemented.
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("Echoview parser expects exactly one input file")

        source_file = file_list[0]

        raise NotImplementedError(
            "Echoview parser not yet implemented. "
            "Requires porting echoviewParse.m (777 lines). "
            "See MATLAB Parser/echoviewParse.m."
        )

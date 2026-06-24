"""FSI NXIC CTD binary parser.

Port of MATLAB NXICBinaryParse.m.
Parses binary .ctd files from Falmouth Scientific Inc (FSI) NXIC CTD instruments.

MATLAB source: Parser/NXICBinaryParse.m (835 lines)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from imos_toolbox.model import IMOSDataset
from imos_toolbox.parsers.base import BaseParser


class NXICParser(BaseParser):
    """Parser for FSI NXIC CTD binary files (.ctd).
    
    Mirrors MATLAB NXICBinaryParse.m. Reads binary CTD data from
    Falmouth Scientific Inc NXIC instruments.
    """

    parser_name = "NXIC"

    def parse(self, filenames: Iterable[str | Path], mode: str) -> IMOSDataset:
        """Parse FSI NXIC CTD binary file.
        
        Args:
            filenames: List of file paths (only first used)
            mode: Toolbox mode
            
        Returns:
            IMOSDataset with TEMP, CNDC, PRES_REL
            
        Raises:
            NotImplementedError: Full binary parsing not yet implemented.
        """
        file_list = [Path(name) for name in filenames]
        if len(file_list) != 1:
            raise ValueError("NXIC parser expects exactly one input file")

        source_file = file_list[0]
        if source_file.suffix.lower() != ".ctd":
            raise ValueError("NXIC parser supports .ctd files only")

        raise NotImplementedError(
            "NXIC binary parser not yet implemented. "
            "Requires porting NXICBinaryParse.m (835 lines). "
            "See MATLAB Parser/NXICBinaryParse.m."
        )

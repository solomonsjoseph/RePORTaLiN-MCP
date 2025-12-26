"""
RePORTaLiN: Clinical Data Pipeline and MCP Server.

This package provides tools for de-identifying clinical data and an MCP server
for secure data access with privacy-preserving aggregations.

Version Information:
    __version__: Current semantic version (MAJOR.MINOR.PATCH format)
    __version_info__: Version as a tuple of integers
"""

import re

__version__: str = "0.3.0"

# Validate semantic versioning format
if not re.match(r"^\d+\.\d+\.\d+$", __version__):
    raise ValueError(
        f"Invalid version format: {__version__}. "
        f"Must follow semantic versioning: MAJOR.MINOR.PATCH"
    )

# Auto-derive version tuple
_parts = tuple(map(int, __version__.split(".")))
__version_info__: tuple[int, int, int] = (_parts[0], _parts[1], _parts[2])

__all__ = ["__version__", "__version_info__"]

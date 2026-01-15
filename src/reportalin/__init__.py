"""
RePORTaLiN: Clinical Data Pipeline and MCP Server.

This package provides tools for de-identifying clinical data and an MCP server
for secure data access with privacy-preserving aggregations.

Version Information:
    __version__: Current semantic version (auto-generated from git tags)
    __version_info__: Version as a tuple of integers
"""

try:
    # Version automatically managed by setuptools-scm from git tags
    from reportalin._version import __version__, __version_tuple__ as _raw_version_tuple
    
    # Extract clean version tuple (major, minor, patch) from setuptools-scm format
    if isinstance(_raw_version_tuple, tuple) and len(_raw_version_tuple) >= 3:
        __version_info__ = (_raw_version_tuple[0], _raw_version_tuple[1], _raw_version_tuple[2])
    else:
        __version_info__ = (0, 0, 0)
except ImportError:
    # Fallback for development without proper install
    __version__ = "0.0.0+unknown"
    __version_info__ = (0, 0, 0)

__all__ = ["__version__", "__version_info__"]

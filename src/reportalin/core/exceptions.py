"""Shared exception classes for the reportalin package.

This module provides all custom exception classes used across the codebase.
Centralizing exceptions here prevents duplication and ensures consistent
error handling patterns.

Exception Hierarchy:
    PrivacyViolationError (DPDPA/HIPAA violations)
    ConfigurationError (invalid configuration)

Usage:
    >>> from reportalin.core.exceptions import ConfigurationError
    >>> raise ConfigurationError("Missing required setting")
"""

from __future__ import annotations


class PrivacyViolationError(Exception):
    """Raised when privacy constraints are violated.

    This exception is raised when operations would violate:
    - DPDPA 2023 (India) privacy requirements
    - HIPAA Privacy Rule (US)
    - Minimum k-anonymity thresholds
    - PHI/PII exposure restrictions

    Attributes:
        k_value: The actual number of records in the result set
        threshold: The minimum k-anonymity threshold required
    """

    def __init__(self, message: str, k_value: int | None = None, threshold: int | None = None):
        super().__init__(message)
        self.k_value = k_value
        self.threshold = threshold


class ConfigurationError(Exception):
    """Raised when configuration is invalid.

    This exception is raised when:
    - Required configuration values are missing
    - Configuration values fail validation
    - Environment-specific requirements are not met
    """

    pass


__all__ = [
    "PrivacyViolationError",
    "ConfigurationError",
]

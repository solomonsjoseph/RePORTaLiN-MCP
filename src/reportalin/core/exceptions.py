"""Shared exception classes for the reportalin package.

This module provides all custom exception classes used across the codebase.
Centralizing exceptions here prevents duplication and ensures consistent
error handling patterns.

Exception Hierarchy:
    EncryptionError (base for crypto errors)
    ├── DecryptionError (decryption failures)

    PrivacyViolationError (DPDPA/HIPAA violations)
    AuthorizationError (access control failures)
    ConfigurationError (invalid configuration)

Usage:
    >>> from reportalin.core.exceptions import DecryptionError
    >>> raise DecryptionError("Invalid key")
"""

from __future__ import annotations


class EncryptionError(Exception):
    """Base class for encryption-related errors.

    Raised when encryption operations fail due to invalid keys,
    corrupted data, or unsupported algorithms.
    """

    pass


class DecryptionError(EncryptionError):
    """Raised when decryption fails.

    This can occur due to:
    - Invalid decryption key
    - Corrupted ciphertext
    - Authentication tag mismatch (GCM mode)
    - Unsupported encryption algorithm
    """

    pass


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


class AuthorizationError(Exception):
    """Raised when authorization checks fail.

    This exception is raised when:
    - User lacks required permissions
    - Access token is invalid or expired
    - Resource access is denied
    """

    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid.

    This exception is raised when:
    - Required configuration values are missing
    - Configuration values fail validation
    - Environment-specific requirements are not met
    """

    pass


__all__ = [
    "EncryptionError",
    "DecryptionError",
    "PrivacyViolationError",
    "AuthorizationError",
    "ConfigurationError",
]

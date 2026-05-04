#!/usr/bin/env python3
"""
AES-256-GCM Authenticated Encryption Module.

This module provides enterprise-grade symmetric encryption using AES-256-GCM,
which is the recommended standard for authenticated encryption in 2025.

Why AES-256-GCM over Fernet (AES-128-CBC)?
    - AES-256: 256-bit key vs Fernet's 128-bit (2^128 more combinations)
    - GCM mode: Provides authentication + encryption in single pass
    - No padding oracle attacks: GCM doesn't require padding
    - NIST approved: Recommended by HIPAA, DPDPA 2025, PCI-DSS

Security Properties:
    - Confidentiality: AES-256 symmetric encryption
    - Integrity: GCM authentication tag (128-bit)
    - Freshness: Random 96-bit nonce per encryption
    - Key derivation: PBKDF2-HMAC-SHA256 for password-based keys

Usage:
    >>> from reportalin.server.security.encryption import AES256GCMCipher
    >>>
    >>> # Generate a new cipher with random key
    >>> cipher = AES256GCMCipher.generate()
    >>>
    >>> # Encrypt data
    >>> encrypted = cipher.encrypt(b"PHI mapping data")
    >>>
    >>> # Decrypt data
    >>> decrypted = cipher.decrypt(encrypted)
    >>>
    >>> # Export key for storage (base64-encoded)
    >>> key_b64 = cipher.export_key()
    >>>
    >>> # Import from existing key
    >>> cipher2 = AES256GCMCipher.from_key(key_b64)

See Also:
    - NIST SP 800-38D: Recommendation for GCM Mode
    - server/security/secrets.py: Key rotation management
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import shared exceptions
from reportalin.core.exceptions import DecryptionError, EncryptionError

__all__ = [
    # Classes
    "AES256GCMCipher",
    "EncryptedPayload",
    # Functions
    "derive_key_from_password",
    # Constants (for advanced users)
    "AES_256_KEY_SIZE",
    "GCM_NONCE_SIZE",
    "GCM_TAG_SIZE",
    "PBKDF2_ITERATIONS",
    "PBKDF2_SALT_SIZE",
]

# Note: DecryptionError and EncryptionError are imported from reportalin.core.exceptions
# Import them from there instead of from this module


# =============================================================================
# Constants
# =============================================================================

# AES-256 requires 32-byte (256-bit) key
AES_256_KEY_SIZE = 32

# GCM standard nonce size: 96 bits (12 bytes)
GCM_NONCE_SIZE = 12

# GCM authentication tag size: 128 bits (16 bytes)
GCM_TAG_SIZE = 16

# PBKDF2 iteration count - OWASP 2024 minimum recommendation
PBKDF2_ITERATIONS = 600_000

# Salt size for PBKDF2
PBKDF2_SALT_SIZE = 32


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class EncryptedPayload:
    """
    Immutable container for encrypted data with all components needed for decryption.

    The payload is serialized as a JSON object with base64-encoded binary fields.
    This format is human-readable and can be safely stored in text-based systems.

    Attributes:
        nonce: Random 96-bit nonce (unique per encryption)
        ciphertext: AES-256-GCM encrypted data with appended auth tag
        version: Encryption format version for future compatibility
        timestamp: Unix timestamp when encryption occurred

    Wire Format (JSON):
        {
            "v": 1,
            "n": "<base64-nonce>",
            "c": "<base64-ciphertext>",
            "t": 1701849600
        }
    """

    nonce: bytes
    ciphertext: bytes
    version: int = 1
    timestamp: float = field(default_factory=time.time)

    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage.

        Returns:
            UTF-8 encoded JSON with base64-encoded binary fields.
        """
        payload = {
            "v": self.version,
            "n": base64.b64encode(self.nonce).decode("ascii"),
            "c": base64.b64encode(self.ciphertext).decode("ascii"),
            "t": self.timestamp,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> EncryptedPayload:
        """Deserialize from bytes.

        Args:
            data: UTF-8 encoded JSON payload.

        Returns:
            EncryptedPayload instance with decoded fields.

        Raises:
            DecryptionError: If payload format is invalid or malformed.
        """
        try:
            payload = json.loads(data.decode("utf-8"))
            return cls(
                nonce=base64.b64decode(payload["n"]),
                ciphertext=base64.b64decode(payload["c"]),
                version=payload.get("v", 1),
                timestamp=payload.get("t", 0.0),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise DecryptionError("Invalid encrypted payload format") from e


# =============================================================================
# Key Derivation
# =============================================================================


def derive_key_from_password(
    password: str,
    salt: bytes | None = None,
    iterations: int = PBKDF2_ITERATIONS,
) -> tuple[bytes, bytes]:
    """
    Derive an AES-256 key from a password using PBKDF2-HMAC-SHA256.

    This function implements secure password-based key derivation following
    OWASP guidelines for 2024+. The high iteration count makes brute-force
    attacks computationally expensive.

    Args:
        password: User-provided password (any length)
        salt: Optional salt bytes. If None, generates a random 32-byte salt.
        iterations: PBKDF2 iteration count (default: 600,000 per OWASP 2024)

    Returns:
        Tuple of (derived_key, salt) where:
        - derived_key: 32-byte AES-256 key
        - salt: Salt used (save this alongside encrypted data)

    Example:
        >>> key, salt = derive_key_from_password("user-password")
        >>> cipher = AES256GCMCipher(key)
        >>> # Store salt with encrypted data for decryption later

    Security Note:
        The salt MUST be stored alongside encrypted data. Without it,
        decryption is impossible even with the correct password.
    """
    if salt is None:
        salt = os.urandom(PBKDF2_SALT_SIZE)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_256_KEY_SIZE,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )

    key = kdf.derive(password.encode("utf-8"))
    return key, salt


# =============================================================================
# Main Cipher Class
# =============================================================================


class AES256GCMCipher:
    """
    AES-256-GCM authenticated encryption cipher.

    This class provides a high-level interface for encrypting and decrypting
    data using AES-256 in GCM mode. GCM (Galois/Counter Mode) provides both
    confidentiality and authenticity in a single operation.

    Thread Safety:
        This class is thread-safe. The underlying AESGCM implementation
        is stateless, and nonces are generated fresh for each encryption.

    Attributes:
        key: The 32-byte AES-256 key (never logged or serialized)

    Example:
        >>> cipher = AES256GCMCipher.generate()
        >>>
        >>> # Encrypt sensitive data
        >>> plaintext = b'{"patient_id": "123", "name": "John Doe"}'
        >>> encrypted = cipher.encrypt(plaintext)
        >>>
        >>> # Later, decrypt
        >>> decrypted = cipher.decrypt(encrypted)
        >>> assert decrypted == plaintext
    """

    __slots__ = ("_aesgcm", "_key")

    def __init__(self, key: bytes) -> None:
        """
        Initialize cipher with an existing key.

        Args:
            key: 32-byte (256-bit) AES key

        Raises:
            EncryptionError: If key length is not exactly 32 bytes

        Note:
            Prefer using `generate()` or `from_key()` factory methods
            instead of calling this constructor directly.
        """
        if len(key) != AES_256_KEY_SIZE:
            raise EncryptionError(
                f"AES-256 requires {AES_256_KEY_SIZE}-byte key, got {len(key)}"
            )

        self._key = key
        self._aesgcm = AESGCM(key)

    @classmethod
    def generate(cls) -> AES256GCMCipher:
        """
        Generate a new cipher with a cryptographically random key.

        Uses `os.urandom()` which sources entropy from the operating
        system's cryptographic random number generator.

        Returns:
            New AES256GCMCipher instance with random 256-bit key

        Example:
            >>> cipher = AES256GCMCipher.generate()
            >>> key_b64 = cipher.export_key()  # Save this securely!
        """
        key = os.urandom(AES_256_KEY_SIZE)
        return cls(key)

    @classmethod
    def from_key(cls, key_b64: str) -> AES256GCMCipher:
        """
        Create cipher from a base64-encoded key.

        Args:
            key_b64: Base64-encoded 32-byte key (as returned by export_key())

        Returns:
            AES256GCMCipher instance

        Raises:
            EncryptionError: If key is invalid or wrong length

        Example:
            >>> key_b64 = "base64encodedkey..."  # From secure storage
            >>> cipher = AES256GCMCipher.from_key(key_b64)
        """
        try:
            key = base64.b64decode(key_b64)
        except ValueError as e:
            raise EncryptionError("Invalid base64 key encoding") from e

        return cls(key)

    @classmethod
    def from_password(
        cls,
        password: str,
        salt: bytes | None = None,
    ) -> tuple[AES256GCMCipher, bytes]:
        """
        Create cipher from a password using PBKDF2 key derivation.

        Args:
            password: User-provided password
            salt: Optional salt (generates new if None)

        Returns:
            Tuple of (cipher, salt) - MUST store salt with encrypted data

        Example:
            >>> cipher, salt = AES256GCMCipher.from_password("my-password")
            >>> encrypted = cipher.encrypt(data)
            >>> # Store both `encrypted` and `salt`
        """
        key, salt = derive_key_from_password(password, salt)
        return cls(key), salt

    def export_key(self) -> str:
        """
        Export the key as base64-encoded string.

        Returns:
            Base64-encoded key string (44 characters)

        Security Warning:
            The exported key provides full access to decrypt all data
            encrypted with this cipher. Store it securely:
            - Use a secrets manager (AWS Secrets Manager, HashiCorp Vault)
            - Never log or include in error messages
            - Never commit to version control
        """
        return base64.b64encode(self._key).decode("ascii")

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: bytes | None = None,
    ) -> EncryptedPayload:
        """
        Encrypt plaintext using AES-256-GCM.

        Each call generates a fresh random nonce to ensure that encrypting
        the same plaintext twice produces different ciphertext.

        Args:
            plaintext: Data to encrypt (any length)
            associated_data: Optional additional authenticated data (AAD).
                            This data is authenticated but not encrypted.
                            Useful for binding metadata to ciphertext.

        Returns:
            EncryptedPayload containing nonce and ciphertext

        Raises:
            EncryptionError: If encryption fails

        Example:
            >>> cipher = AES256GCMCipher.generate()
            >>> payload = cipher.encrypt(b"sensitive data")
            >>> # Store payload.to_bytes() in database
        """
        try:
            # Generate random nonce for this encryption
            nonce = os.urandom(GCM_NONCE_SIZE)

            # Encrypt with optional AAD
            ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)

            return EncryptedPayload(
                nonce=nonce,
                ciphertext=ciphertext,
                version=1,
                timestamp=time.time(),
            )

        except Exception as e:
            raise EncryptionError(f"Encryption failed: {type(e).__name__}") from e

    def decrypt(
        self,
        payload: EncryptedPayload | bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """
        Decrypt ciphertext using AES-256-GCM.

        The authentication tag is verified before decryption. If the tag
        doesn't match (indicating tampering or wrong key), decryption fails.

        Args:
            payload: EncryptedPayload or serialized bytes to decrypt
            associated_data: Must match the AAD used during encryption

        Returns:
            Decrypted plaintext bytes

        Raises:
            DecryptionError: If decryption fails for any reason including:
                - Invalid payload format
                - Authentication tag mismatch (tampering)
                - Wrong key
                - Corrupted data

        Security Note:
            The exception message is intentionally vague to prevent
            information leakage. Detailed errors are logged server-side.
        """
        # Parse bytes if needed
        if isinstance(payload, bytes):
            payload = EncryptedPayload.from_bytes(payload)

        # Validate payload version
        if payload.version != 1:
            raise DecryptionError(f"Unsupported encryption version: {payload.version}")

        try:
            plaintext = self._aesgcm.decrypt(
                payload.nonce,
                payload.ciphertext,
                associated_data,
            )
            return plaintext

        except Exception:
            # Don't expose cryptographic details in exception
            raise DecryptionError("Decryption failed - invalid key or corrupted data")

    def encrypt_string(self, plaintext: str) -> str:
        """Convenience method to encrypt a string and return base64.

        Args:
            plaintext: UTF-8 string to encrypt.

        Returns:
            Base64-encoded encrypted payload string.

        Raises:
            EncryptionError: If encryption fails.
        """
        payload = self.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(payload.to_bytes()).decode("ascii")

    def decrypt_string(self, ciphertext_b64: str) -> str:
        """Convenience method to decrypt a base64 string.

        Args:
            ciphertext_b64: Base64-encoded encrypted payload.

        Returns:
            Decrypted UTF-8 string.

        Raises:
            DecryptionError: If decryption fails.
        """
        payload_bytes = base64.b64decode(ciphertext_b64)
        plaintext = self.decrypt(payload_bytes)
        return plaintext.decode("utf-8")

    def __repr__(self) -> str:
        """Return safe representation that doesn't expose the key.

        Returns:
            String representation with truncated key hash.
        """
        return f"<AES256GCMCipher key_hash={hash(self._key) & 0xFFFF:04x}>"

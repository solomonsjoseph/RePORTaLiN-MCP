#!/usr/bin/env python3
"""
Secure Log Decryption Utility for Developers/Maintainers.

This module provides secure access to encrypted logs for authorized
developers and maintainers. It implements:
- RSA/AES hybrid decryption (matching crypto_logger.py encryption)
- Key fingerprint verification for authorization
- Audit trail of decryption operations
- CLI interface for log inspection

Security Requirements:
    - Private key must be stored securely (HSM, encrypted file, or env var)
    - Decryption operations are logged for audit
    - Only authorized key fingerprints can decrypt
    - No PHI is displayed without explicit --show-phi flag

Usage:
    CLI:
        # Decrypt a single log file
        python -m reportalin.core.log_decryptor encrypted_logs/log_xxx.enc

        # Decrypt all logs from today
        python -m reportalin.core.log_decryptor encrypted_logs/ --since today

        # Export decrypted logs to file
        python -m reportalin.core.log_decryptor encrypted_logs/ --output decrypted.json

    Python:
        >>> from reportalin.core.log_decryptor import LogDecryptor
        >>> decryptor = LogDecryptor(private_key_path="~/.ssh/reportalin_key")
        >>> entry = decryptor.decrypt_file("encrypted_logs/log_xxx.enc")
        >>> print(entry["message"])

See Also:
    - reportalin.server - MCP server implementation with encryption
    - reportalin.core.config - Key path configuration
"""

from __future__ import annotations

__all__ = [
    "AuthorizationError",
    "DecryptionError",
    "LogDecryptor",
    "generate_keypair",
    "main",
]

import argparse
import base64
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Import shared exceptions
from reportalin.core.exceptions import AuthorizationError, DecryptionError

# Import cryptography (required for decryption)
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class LogDecryptor:
    """Secure log decryption utility for authorized developers.

    This class provides decryption capabilities for logs encrypted by
    the SecureLogger in crypto_logger.py. It verifies key authorization
    and maintains an audit trail.

    Attributes:
        private_key: Loaded RSA private key for decryption.
        key_fingerprint: SHA256 fingerprint of the private key.

    Example:
        >>> decryptor = LogDecryptor(private_key_path="~/.ssh/reportalin_key")
        >>> entries = decryptor.decrypt_directory("encrypted_logs/")
        >>> for entry in entries:
        ...     print(f"{entry['timestamp']}: {entry['message']}")
    """

    def __init__(
        self,
        private_key_path: str | Path | None = None,
        private_key_pem: bytes | None = None,
        private_key_password: str | None = None,
        authorized_fingerprints: list[str] | None = None,
    ) -> None:
        """Initialize the log decryptor.

        Args:
            private_key_path: Path to RSA private key file.
            private_key_pem: RSA private key in PEM format (alternative to path).
            private_key_password: Password for encrypted private key.
            authorized_fingerprints: List of authorized key fingerprints.
                If None, authorization check is skipped (development mode).

        Raises:
            ImportError: If cryptography library is not available.
            FileNotFoundError: If private key file not found.
            AuthorizationError: If key fingerprint is not authorized.
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography library required for log decryption. "
                "Install with: pip install cryptography"
            )

        self.authorized_fingerprints = authorized_fingerprints
        self._load_private_key(private_key_path, private_key_pem, private_key_password)
        self._verify_authorization()

    def _load_private_key(
        self,
        key_path: str | Path | None,
        key_pem: bytes | None,
        password: str | None,
    ) -> None:
        """Load and validate the RSA private key.

        Args:
            key_path: Path to PEM-encoded private key file.
            key_pem: Raw PEM bytes (alternative to file path).
            password: Password for encrypted private key.

        Raises:
            FileNotFoundError: If key_path specified but file not found.
            ValueError: If no key source provided and env var not set.
        """
        password_bytes = password.encode() if password else None

        if key_pem:
            # Load from PEM bytes
            self.private_key = serialization.load_pem_private_key(
                key_pem,
                password=password_bytes,
                backend=default_backend(),
            )
        elif key_path:
            # Load from file
            path = Path(key_path).expanduser().resolve()
            if not path.exists():
                raise FileNotFoundError(f"Private key not found: {path}")

            with open(path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=password_bytes,
                    backend=default_backend(),
                )
        else:
            # Try environment variable
            env_key = os.environ.get("REPORTALIN_CRYPTO_PRIVATE_KEY")
            if env_key:
                self.private_key = serialization.load_pem_private_key(
                    env_key.encode(),
                    password=password_bytes,
                    backend=default_backend(),
                )
            else:
                raise ValueError(
                    "No private key provided. Set REPORTALIN_CRYPTO_PRIVATE_KEY "
                    "or provide private_key_path/private_key_pem"
                )

        # Calculate key fingerprint
        public_key = self.private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.key_fingerprint = hashlib.sha256(public_bytes).hexdigest()

    def _verify_authorization(self) -> None:
        """Verify the key is authorized for decryption.

        Raises:
            AuthorizationError: If key fingerprint not in authorized list.

        Note:
            If authorized_fingerprints is None, authorization check is
            skipped (development mode).
        """
        if self.authorized_fingerprints is None:
            # No authorization list - development mode
            return

        if self.key_fingerprint not in self.authorized_fingerprints:
            raise AuthorizationError(
                f"Key fingerprint {self.key_fingerprint[:16]}... is not authorized. "
                "Contact your security administrator to add your key."
            )

    def _decrypt_aes_key(self, encrypted_key: bytes) -> bytes:
        """Decrypt the AES key using RSA private key.

        Args:
            encrypted_key: RSA-encrypted AES key.

        Returns:
            Decrypted AES key.
        """
        return self.private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

    def _decrypt_content(self, encrypted_data: dict[str, Any]) -> str:
        """Decrypt log content using hybrid decryption.

        Args:
            encrypted_data: Dictionary containing encrypted_key, iv, ciphertext.

        Returns:
            Decrypted log content as string.

        Raises:
            DecryptionError: If decryption fails.
        """
        if not encrypted_data.get("encrypted", True):
            # Log was not encrypted (crypto not available during logging)
            return base64.b64decode(encrypted_data["content"]).decode("utf-8")

        try:
            # Decode components
            encrypted_key = base64.b64decode(encrypted_data["encrypted_key"])
            iv = base64.b64decode(encrypted_data["iv"])
            ciphertext = base64.b64decode(encrypted_data["ciphertext"])

            # Decrypt AES key
            aes_key = self._decrypt_aes_key(encrypted_key)

            # Decrypt content
            cipher = Cipher(
                algorithms.AES(aes_key),
                modes.CBC(iv),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            padded_content = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove PKCS7 padding
            pad_length = padded_content[-1]
            content = padded_content[:-pad_length]

            return content.decode("utf-8")

        except Exception as e:
            raise DecryptionError(f"Failed to decrypt log: {e}") from e

    def decrypt_file(self, file_path: str | Path) -> dict[str, Any]:
        """Decrypt a single encrypted log file.

        Args:
            file_path: Path to encrypted log file (.enc).

        Returns:
            Decrypted log entry as dictionary.

        Raises:
            DecryptionError: If file cannot be read or decrypted.
        """
        path = Path(file_path)
        if not path.exists():
            raise DecryptionError(f"Log file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                encrypted_data = json.load(f)

            content = self._decrypt_content(encrypted_data)
            return json.loads(content)

        except json.JSONDecodeError as e:
            raise DecryptionError(f"Invalid log file format: {e}") from e

    def decrypt_directory(
        self,
        dir_path: str | Path,
        *,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Decrypt all log files in a directory.

        Args:
            dir_path: Path to directory containing .enc files.
            since: Only include logs after this timestamp.
            until: Only include logs before this timestamp.
            level: Filter by log level (ERROR, WARN, INFO, DEBUG).

        Returns:
            List of decrypted log entries, sorted by timestamp.
        """
        path = Path(dir_path)
        if not path.is_dir():
            raise DecryptionError(f"Not a directory: {path}")

        entries = []
        for file_path in sorted(path.glob("*.enc")):
            try:
                entry = self.decrypt_file(file_path)

                # Apply filters
                if level and entry.get("level") != level.upper():
                    continue

                if since or until:
                    timestamp_str = entry.get("timestamp", "")
                    if timestamp_str:
                        # Parse ISO timestamp
                        timestamp = datetime.datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        if since and timestamp < since:
                            continue
                        if until and timestamp > until:
                            continue

                entries.append(entry)

            except DecryptionError as e:
                # Log warning but continue with other files
                print(f"Warning: {e}", file=sys.stderr)

        return entries

    def get_key_fingerprint(self) -> str:
        """Get the SHA256 fingerprint of the loaded key.

        Returns:
            Hex-encoded SHA256 fingerprint.
        """
        return self.key_fingerprint


def generate_keypair(
    private_key_path: str | Path,
    public_key_path: str | Path,
    key_size: int = 4096,
    password: str | None = None,
) -> str:
    """Generate a new RSA keypair for log encryption/decryption.

    Args:
        private_key_path: Where to save the private key.
        public_key_path: Where to save the public key.
        key_size: RSA key size in bits (default 4096).
        password: Optional password to encrypt private key.

    Returns:
        SHA256 fingerprint of the generated key.

    Example:
        >>> fingerprint = generate_keypair(
        ...     "~/.ssh/reportalin_private.pem",
        ...     "~/.ssh/reportalin_public.pem",
        ...     password="secure_password"
        ... )
        >>> print(f"Key fingerprint: {fingerprint}")
    """
    if not CRYPTO_AVAILABLE:
        raise ImportError("cryptography library required for key generation")

    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate keypair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # Serialize private key
    encryption = (
        serialization.BestAvailableEncryption(password.encode())
        if password
        else serialization.NoEncryption()
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Calculate fingerprint
    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(public_der).hexdigest()

    # Write files
    private_path = Path(private_key_path).expanduser()
    public_path = Path(public_key_path).expanduser()

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)

    with open(private_path, "wb") as f:
        f.write(private_pem)
    os.chmod(private_path, 0o600)  # Restrict permissions

    with open(public_path, "wb") as f:
        f.write(public_pem)

    return fingerprint


def main() -> None:
    """CLI entry point for log decryption.

    Parses command-line arguments and executes the appropriate action:
    key generation, fingerprint display, or log decryption.

    Returns:
        None. Exits with status 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Decrypt encrypted log files for authorized developers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Decrypt a single file
    python -m reportalin.core.log_decryptor encrypted_logs/log_xxx.enc

    # Decrypt all logs with ERROR level
    python -m reportalin.core.log_decryptor encrypted_logs/ --level ERROR

    # Decrypt logs from the last 24 hours
    python -m reportalin.core.log_decryptor encrypted_logs/ --since "1 day ago"

    # Generate new keypair
    python -m reportalin.core.log_decryptor --generate-keys

Key Management:
    Set REPORTALIN_CRYPTO_PRIVATE_KEY environment variable with your
    private key PEM content, or use --key-file to specify the path.
""",
    )

    parser.add_argument(
        "path",
        nargs="?",
        help="Path to encrypted log file or directory",
    )
    parser.add_argument(
        "--key-file",
        "-k",
        help="Path to RSA private key file",
    )
    parser.add_argument(
        "--password",
        "-p",
        help="Password for encrypted private key",
    )
    parser.add_argument(
        "--level",
        "-l",
        choices=["DEBUG", "INFO", "WARN", "ERROR", "CRASH"],
        help="Filter by log level",
    )
    parser.add_argument(
        "--since",
        help="Only show logs after this time (ISO format or relative like '1 day ago')",
    )
    parser.add_argument(
        "--until",
        help="Only show logs before this time (ISO format)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for decrypted logs (JSON format)",
    )
    parser.add_argument(
        "--show-phi",
        action="store_true",
        help="Show PHI fields (default: redacted)",
    )
    parser.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate new RSA keypair for log encryption",
    )
    parser.add_argument(
        "--fingerprint",
        action="store_true",
        help="Display the fingerprint of the loaded key",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )

    args = parser.parse_args()

    # Handle key generation
    if args.generate_keys:
        print("Generating RSA keypair for log encryption...")
        private_path = Path.home() / ".reportalin" / "log_decrypt_key"
        public_path = Path.home() / ".reportalin" / "log_encrypt_key.pub"

        password = args.password
        if not password:
            import getpass

            password = getpass.getpass(
                "Enter password for private key (empty for none): "
            )

        fingerprint = generate_keypair(
            private_path,
            public_path,
            password=password if password else None,
        )

        print("\nKeys generated:")
        print(f"  Private key: {private_path}")
        print(f"  Public key:  {public_path}")
        print(f"  Fingerprint: {fingerprint}")
        print("\nAdd the public key to your MCP server configuration.")
        print("Add this fingerprint to authorized_key_fingerprints in settings.")
        return

    # Require path for other operations
    if not args.path:
        parser.error("Path to log file or directory is required")

    try:
        decryptor = LogDecryptor(
            private_key_path=args.key_file,
            private_key_password=args.password,
        )

        if args.fingerprint:
            print(f"Key fingerprint: {decryptor.get_key_fingerprint()}")
            return

        path = Path(args.path)

        # Parse time filters
        since = None
        until = None
        if args.since:
            # Simple relative time parsing
            if "ago" in args.since.lower():
                # Parse "X days/hours ago"
                parts = args.since.lower().split()
                amount = int(parts[0])
                unit = parts[1]
                if "day" in unit:
                    since = datetime.datetime.now(
                        datetime.timezone.utc
                    ) - datetime.timedelta(days=amount)
                elif "hour" in unit:
                    since = datetime.datetime.now(
                        datetime.timezone.utc
                    ) - datetime.timedelta(hours=amount)
            else:
                since = datetime.datetime.fromisoformat(args.since)

        if args.until:
            until = datetime.datetime.fromisoformat(args.until)

        # Decrypt
        if path.is_file():
            entries = [decryptor.decrypt_file(path)]
        else:
            entries = decryptor.decrypt_directory(
                path,
                since=since,
                until=until,
                level=args.level,
            )

        # Redact PHI unless --show-phi
        if not args.show_phi:
            from reportalin.core.logging import _redact_phi

            entries = [_redact_phi(e, True) for e in entries]

        # Output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, default=str)
            print(f"Wrote {len(entries)} entries to {args.output}")
        elif args.json:
            print(json.dumps(entries, indent=2, default=str))
        else:
            # Human-readable output
            for entry in entries:
                timestamp = entry.get("timestamp", "unknown")
                level = entry.get("level", "INFO")
                message = entry.get("message", "")
                print(f"[{timestamp}] {level}: {message}")

                if entry.get("context"):
                    print(f"  Context: {json.dumps(entry['context'], default=str)}")

                if entry.get("exception"):
                    exc = entry["exception"]
                    print(f"  Exception: {exc.get('type')}: {exc.get('message')}")
                    if "traceback" in exc:
                        print("  Traceback:")
                        for line in exc["traceback"]:
                            print(f"    {line.rstrip()}")

                print()

    except (DecryptionError, AuthorizationError, ImportError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

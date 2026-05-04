# ADR-0002: AES-256-GCM Over Fernet

## Status

Accepted

## Context

The RePORTaLiN system handles Protected Health Information (PHI) that must be encrypted at rest. We needed to choose an encryption standard that meets:

1. HIPAA compliance requirements
2. DPDPA 2025 (India) data protection standards
3. NIST recommendations for 2025+
4. Performance requirements for real-time operations

The previous implementation used **Fernet** (AES-128-CBC with HMAC-SHA256).

## Decision

We will use **AES-256-GCM** (Galois/Counter Mode) for all symmetric encryption operations.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Constants
AES_256_KEY_SIZE = 32      # 256-bit key
GCM_NONCE_SIZE = 12        # 96-bit nonce (NIST recommended)
PBKDF2_ITERATIONS = 600000  # OWASP 2024 minimum
```

## Consequences

### Positive

- **Stronger encryption**: 256-bit vs 128-bit key (2^128 more combinations)
- **Authenticated encryption**: GCM provides encryption + authentication in single pass
- **No padding oracle attacks**: GCM mode doesn't require padding
- **NIST SP 800-38D compliance**: Recommended for sensitive data
- **Performance**: GCM is parallelizable and often hardware-accelerated (AES-NI)
- **Compliance**: Meets HIPAA, DPDPA 2025, and PCI-DSS requirements

### Negative

- **Nonce management**: Must never reuse nonce with same key (handled by random generation)
- **Migration required**: Existing Fernet-encrypted files need migration path
- **Slightly larger output**: 12-byte nonce + 16-byte auth tag overhead

### Neutral

- Key derivation uses PBKDF2-HMAC-SHA256 (same as Fernet)
- Backward compatibility maintained via Fernet fallback for legacy files

## Alternatives Considered

### Keep Fernet (AES-128-CBC)

- Simpler API
- Proven track record

Not chosen because: 128-bit keys are below NIST recommendations for 2025+, and CBC mode is vulnerable to padding oracle attacks if implemented incorrectly.

### ChaCha20-Poly1305

- Excellent performance without hardware acceleration
- Modern authenticated encryption

Not chosen because: AES-256-GCM has broader compliance recognition and hardware acceleration on most servers.

### XChaCha20-Poly1305

- Extended nonce (192-bit) eliminates nonce reuse concerns

Not chosen because: Less compliance documentation and not as widely audited for healthcare use cases.

## References

- [NIST SP 800-38D: GCM Mode](https://csrc.nist.gov/publications/detail/sp/800-38d/final)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [Cryptography library documentation](https://cryptography.io/en/latest/hazmat/primitives/aead/)

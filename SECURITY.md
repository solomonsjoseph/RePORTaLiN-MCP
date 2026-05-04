# Security Policy

<!--
Document Type: Reference (Diátaxis)
Target Audience: Developers, operators, and security auditors
Prerequisites: None
-->

> **Type**: Reference | **Updated**: 2025-12-04 | **Version**: 1.0

This document outlines security policies, compliance requirements, and vulnerability reporting for RePORTaLiN-Specialist.

**Related Documentation:**
- [Logging Architecture](docs/LOGGING_ARCHITECTURE.md) — Encrypted audit logging
- [Configuration Reference](docs/CONFIGURATION.md) — Security settings
- [Contributing Guidelines](CONTRIBUTING.md) — PHI handling for contributors

---

## Overview

RePORTaLiN-Specialist processes **Protected Health Information (PHI)** and **Personally Identifiable Information (PII)**. This document outlines security policies, compliance requirements, and vulnerability reporting procedures.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.0.x   | :white_check_mark: |

## Compliance Standards

This project is designed to comply with:

| Regulation | Region | Key Requirements |
|------------|--------|------------------|
| **HIPAA** | USA | PHI encryption, audit trails, minimum necessary |
| **GDPR** | EU | Data minimization, right to erasure, consent |
| **DPDPA 2023 + DPDP Rules 2025** | India | Aadhaar/ABHA protection, Data Fiduciary obligations |
| **LGPD** | Brazil | Similar to GDPR with local adaptations |
| **POPIA** | South Africa | Processing limitations, security safeguards |

## Security Architecture

### 1. Encrypted Logging

All sensitive operations are logged with RSA-OAEP + AES-256-CBC hybrid encryption:

```
Log Entry → PHI Redaction → AES-256-CBC Encryption → RSA Key Wrap → .enc file
```

- **Key Rotation**: 90-day rotation period (NIST guideline)
- **PHI Redaction**: Automatic pattern-based redaction before encryption
- **Audit Trail**: Key fingerprints and timestamps in all log entries

### 2. PHI/PII Detection

The system detects and protects 21+ PHI pattern categories:

- **Universal**: Name, SSN, DOB, Address, Phone, Email
- **Medical**: MRN, Patient ID, Hospital ID
- **India-specific**: Aadhaar, PAN, ABHA, UHID, Voter ID
- **Technical**: IP Address, MAC Address, Biometrics

### 3. Data Access Controls

| Data Source | Access Level |
|-------------|--------------|
| Data Dictionary (metadata) | ✅ Allowed |
| Aggregate Statistics | ✅ Allowed (k≥5) |
| De-identified Data | ⚠️ Blocked by default |
| Raw Dataset | ❌ Never accessed |
| PHI Fields | ❌ Always redacted |

### 4. K-Anonymity Protection

All statistical outputs enforce k-anonymity with minimum cell size of 5:

```python
if count < 5:
    return "<5"  # Suppress small counts
```

## Security Best Practices

### For Developers

1. **Never commit secrets** - Use `.env` files (gitignored)
2. **Never log PHI** - Use aggregate values or hashes
3. **Use encrypted logging** - `get_secure_logger()` for sensitive ops
4. **Validate inputs** - All tool inputs are Pydantic-validated
5. **Rotate keys** - Generate new keys every 90 days

### For Operators

1. **Secure key storage** - Use HSM or encrypted file storage
2. **Restrict log access** - Only authorized personnel decrypt logs
3. **Monitor key rotation** - Heed 90-day warnings
4. **Network isolation** - Use stdio transport for MCP server
5. **Audit log retention** - Retain per DPDP Rules 2025 (minimum 1 year)

## Key Management

### Generating Keys

```bash
python -m scripts.core.log_decryptor --generate-keys
```

Keys are stored in:
- Private: `~/.reportalin/log_decrypt_key` (chmod 600)
- Public: `~/.reportalin/log_encrypt_key.pub`

### Key Fingerprints

Add authorized developer fingerprints to:
```bash
REPORTALIN_CRYPTO_AUTHORIZED_KEY_FINGERPRINTS=abc123...,def456...
```

## Reporting a Vulnerability

### Responsible Disclosure

If you discover a security vulnerability:

1. **Do NOT** create a public GitHub issue
2. **Email**: [security contact - add your email here]
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes

### Response Timeline

| Stage | Timeline |
|-------|----------|
| Acknowledgment | 48 hours |
| Initial Assessment | 7 days |
| Fix Development | 30 days (critical: 7 days) |
| Public Disclosure | After fix is deployed |

## Security Checklist

### Before Deployment

- [ ] Replace placeholder encryption key with production key
- [ ] Configure authorized key fingerprints
- [ ] Enable strict privacy mode (`REPORTALIN_PRIVACY_MODE=strict`)
- [ ] Verify k-anonymity threshold is set (default: 5)
- [ ] Ensure encrypted_logs/ has restricted permissions
- [ ] Test decryption with authorized key
- [ ] Review audit logs for any PHI exposure

### During Operation

- [ ] Monitor key rotation warnings
- [ ] Review encrypted logs periodically
- [ ] Audit access to decryption keys
- [ ] Verify no raw PHI in console output
- [ ] Check for unauthorized tool invocations

## Security Contacts

- **Project Security Lead**: [Add contact]
- **Data Protection Officer**: [Add contact]

---

**Last Updated**: 2025-12-04  
**Document Version**: 1.0

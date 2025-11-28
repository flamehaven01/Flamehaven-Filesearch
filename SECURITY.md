# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          | Security Status |
| ------- | ------------------ | --------------- |
| 1.1.x   | ✅ Yes            | Actively maintained, all critical CVEs patched |
| 1.0.x   | ⚠️ Critical only | Upgrade to 1.1.0 recommended |
| < 1.0   | ❌ No             | Unsupported, upgrade required |

**Current Stable**: v1.1.0 (Released 2025-11-13)
**Security Rating**: SIDRCE Certified 0.94 • Zero CRITICAL vulnerabilities

---

## Security Features in v1.1.0

### 🔒 Vulnerability Fixes

#### 1. Path Traversal Protection (CVE-2025-XXXX)
**Severity**: CRITICAL
**Fixed in**: v1.1.0

**Vulnerability**: File upload endpoints allowed directory traversal attacks via `../../` in filenames.

**Attack Vectors Blocked**:
```
../../etc/passwd
../../../windows/system32/config/sam
.env
.hidden_malware.exe
```

**Fix**: Implemented `os.path.basename()` sanitization in `api.py:165, 213`
```python
safe_filename = os.path.basename(file.filename)
if not safe_filename or safe_filename.startswith('.'):
    raise HTTPException(status_code=400, detail="Invalid filename")
```

**Impact**: Prevented arbitrary file write and information disclosure attacks.

#### 2. Starlette CVE-2024-47874 and CVE-2025-54121
**Severity**: CRITICAL
**Fixed in**: v1.1.0

**Vulnerability**: DoS vulnerabilities in multipart form parsing and file uploads.

**Fix**: Upgraded dependencies
- FastAPI 0.104.0 → 0.121.1
- Starlette 0.38.6 → 0.49.3

**Impact**: Prevented denial-of-service attacks via malformed multipart requests.

### 🛡️ Security Enhancements

#### Rate Limiting
Protects against brute-force and abuse attacks.

**Limits** (per IP address):
- Upload single file: 10 requests/minute
- Upload multiple files: 5 requests/minute
- Search queries: 100 requests/minute
- Store management: 20 requests/minute
- Monitoring endpoints: 100 requests/minute

**Implementation**: slowapi with per-IP tracking
**Response**: HTTP 429 with `Retry-After` header

#### OWASP Security Headers
All API responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

#### Input Validation
Comprehensive validation prevents injection attacks:

**FilenameValidator**:
- Path traversal patterns: `..`, `^/`, `^\`, `^[A-Za-z]:`
- Invalid characters: `<>:"|?*\x00-\x1f`
- Hidden files: `.` prefix blocked
- Empty filenames: Rejected

**SearchQueryValidator**:
- XSS detection: `<script>`, `onerror=`, `onclick=`
- SQL injection detection: `'; DROP TABLE`, `UNION SELECT`, `--`
- Length limits: 1-1000 characters

**FileSizeValidator**:
- Maximum file size: 50MB (configurable)
- Human-readable error messages

#### Request Tracing
**X-Request-ID header** for audit trails:
- UUID v4 generation for all requests
- Request ID in logs, error responses, metrics
- Distributed tracing support

### 📊 Security Monitoring

#### Prometheus Metrics
Track security events:
```
rate_limit_exceeded_total{endpoint="/api/upload/single"} 15
errors_total{error_type="InvalidFilenameError",endpoint="/api/upload/single"} 3
errors_total{error_type="FileSizeExceededError",endpoint="/api/upload/single"} 7
```

#### Structured Logging
All security events logged with:
- Request ID
- Timestamp (ISO 8601)
- Error type and message
- Source IP address
- Endpoint and method

**Example JSON log**:
```json
{
  "timestamp": "2025-11-13T12:00:00Z",
  "level": "WARNING",
  "logger": "flamehaven_filesearch.api",
  "message": "Path traversal attempt blocked",
  "request_id": "a1b2c3d4-5678",
  "filename": "../../etc/passwd",
  "source_ip": "192.168.1.100",
  "endpoint": "/api/upload/single"
}
```

---

## Reporting a Vulnerability

### Responsible Disclosure

We take security seriously. If you discover a security vulnerability, please report it responsibly.

**DO NOT** open a public GitHub issue for security vulnerabilities.

### How to Report

**Email**: security@flamehaven.space
**PGP Key**: Available at https://flamehaven.space/pgp-key.asc

**Include**:
1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if available)
5. Your name and contact info (optional, for credit)

### Response Timeline

| Stage | Timeframe |
|-------|-----------|
| Initial response | 24-48 hours |
| Severity assessment | 3-5 business days |
| Fix development | 7-14 days (CRITICAL), 30 days (HIGH) |
| Public disclosure | After fix is released |

### Acknowledgments

We maintain a [Security Hall of Fame](https://github.com/flamehaven01/Flamehaven-Filesearch/wiki/Security-Hall-of-Fame) for responsible disclosure.

---

## Security Best Practices

### Production Deployment

#### API Key Management
```bash
# Use environment variables, NEVER commit to git
export GEMINI_API_KEY="your-key-here"

# Or use secrets management
kubectl create secret generic flamehaven-secrets \
  --from-literal=gemini-api-key="your-key"
```

#### Reverse Proxy with SSL
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name filesearch.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### Firewall Configuration
```bash
# Allow only HTTPS traffic
ufw default deny incoming
ufw default allow outgoing
ufw allow 443/tcp
ufw enable
```

#### Worker Process Isolation
```bash
# Run with minimal privileges
useradd -r -s /bin/false flamehaven
chown -R flamehaven:flamehaven /app/data

# Start with restricted user
su -s /bin/bash flamehaven -c "flamehaven-api"
```

#### Data Encryption at Rest
```bash
# Encrypt data directory with LUKS
cryptsetup luksFormat /dev/sdb1
cryptsetup open /dev/sdb1 flamehaven-data
mkfs.ext4 /dev/mapper/flamehaven-data
mount /dev/mapper/flamehaven-data /app/data
```

#### Regular Security Audits
```bash
# Run automated security scans
pip install bandit safety
bandit -r flamehaven_filesearch/
safety check --json
```

### Development Security

#### Pre-commit Hooks
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Hooks run automatically on git commit:
# - bandit (SAST)
# - gitleaks (secrets scanning)
# - flake8 (linting)
# - custom security checks
```

#### Dependency Management
```bash
# Keep dependencies up to date
pip install -U flamehaven-filesearch[api]

# Check for vulnerabilities
pip-audit
safety check
```

#### Secret Scanning
```bash
# Scan git history for secrets
gitleaks detect --source . --verbose
trufflehog git file://. --only-verified
```

---

## Security Checklist

### Before Production Deployment

- [ ] ✅ API keys in environment variables (not committed)
- [ ] ✅ HTTPS enabled with valid SSL certificate
- [ ] ✅ Reverse proxy configured (nginx/Apache)
- [ ] ✅ Firewall rules: Allow 443, deny all else
- [ ] ✅ Worker processes run with restricted user
- [ ] ✅ Data directory encrypted at rest
- [ ] ✅ Rate limiting configured
- [ ] ✅ Monitoring and alerting set up
- [ ] ✅ Backup strategy in place
- [ ] ✅ Incident response plan documented

### Regular Maintenance

- [ ] Weekly: Review security logs and metrics
- [ ] Monthly: Update dependencies, security scan
- [ ] Quarterly: Penetration testing, vulnerability assessment
- [ ] Annually: Security policy review, compliance audit

---

## Known Limitations

### v1.1.0 Scope

**In Scope**:
- API endpoint security (rate limiting, input validation)
- Transport layer security (HTTPS recommended)
- Path traversal protection
- CVE patching
- Security headers (OWASP compliant)

**Out of Scope** (future enhancements):
- Authentication/authorization (planned for v1.2.0)
- End-to-end encryption
- Multi-tenancy isolation
- Advanced DDoS protection (use CloudFlare/AWS WAF)
- Database encryption (no database, filesystem-based)

### Threat Model

**Protected Against**:
- ✅ Path traversal attacks
- ✅ XSS/SQL injection attempts
- ✅ Brute-force attacks (rate limiting)
- ✅ Known CVEs (Starlette, FastAPI)
- ✅ Information disclosure

**Requires External Protection**:
- ⚠️ DDoS attacks (use CloudFlare, AWS Shield)
- ⚠️ Advanced persistent threats (APTs)
- ⚠️ Physical server access
- ⚠️ Social engineering attacks

---

## Compliance

### Data Privacy

**GDPR Compliance**:
- Data stored locally (DATA_DIR)
- No data sent to third parties except Gemini API
- User can delete all data (DELETE /stores/{name})
- Request logs include request IDs for audit trails

**Gemini API**: See [Google's Privacy Policy](https://policies.google.com/privacy)

### Security Standards

**Aligned with**:
- OWASP Top 10 (2021)
- CWE Top 25 Most Dangerous Software Weaknesses
- NIST Cybersecurity Framework

**Certifications**:
- SIDRCE Certified (0.94)
- Zero CRITICAL vulnerabilities (Bandit, Safety)

---

## Security Resources

### Internal Documentation
- [PHASE1_COMPLETION_SUMMARY.md](PHASE1_COMPLETION_SUMMARY.md) - Security fixes
- [PHASE2_COMPLETION_SUMMARY.md](PHASE2_COMPLETION_SUMMARY.md) - Automated security testing
- [PHASE3_COMPLETION_SUMMARY.md](PHASE3_COMPLETION_SUMMARY.md) - Input validation
- [.golden_baseline.json](.golden_baseline.json) - Security baseline

### External References
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Starlette Security](https://www.starlette.io/security/)

### Security Tools
- **Bandit**: SAST for Python
- **Safety**: Dependency vulnerability scanner
- **Gitleaks**: Secrets scanning in git history
- **TruffleHog**: High-entropy secrets detection

---

## Admin & Encryption (v1.2.x)

- Admin routes require `FLAMEHAVEN_ADMIN_KEY` **or** an API key that includes the `admin` permission. Keys without `admin` receive 403.
- Sensitive admin payloads (key names, permissions) are encrypted at rest with `FLAMEHAVEN_ENC_KEY` (32-byte base64, AES-256-GCM/Fernet). Configure this in secrets before production.
- Cache controls (`/api/admin/cache/stats`, `/api/admin/cache/flush`) are restricted to admin tokens only.
- Optional OIDC validation: set `FLAMEHAVEN_IAM_PROVIDER=oidc` with `FLAMEHAVEN_OIDC_SECRET` (+ optional `FLAMEHAVEN_OIDC_ISSUER`/`FLAMEHAVEN_OIDC_AUDIENCE`). Tokens failing validation are rejected.

---

## Contact

**Security Team**: security@flamehaven.space
**General Support**: info@flamehaven.space
**GitHub Issues**: https://github.com/flamehaven01/Flamehaven-Filesearch/issues (non-security only)

---

**Last Updated**: 2025-11-13
**Document Version**: 1.0.0 (aligned with v1.1.0 release)

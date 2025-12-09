# Upgrading to v1.2.2

This guide covers the upgrade process from **v1.1.x -> v1.2.2**.

---

## TL;DR (Quick Upgrade)

```bash
# 1. Backup data (optional but recommended)
cp -r ./data ./data_backup_v1.0.0

# 2. Upgrade package
pip install -U flamehaven-filesearch[api]

# 3. Restart service
# No configuration changes required - fully backward compatible
flamehaven-api
```

**Breaking Changes**: ⚠️ Admin routes now require `admin` permission on API keys (or `FLAMEHAVEN_ADMIN_KEY`). Set `FLAMEHAVEN_ENC_KEY` for encrypted metadata. Optional OIDC admin validation supported.

---

## What's New in v1.2.2

### Security / Admin
- Admin API 키는 `admin` 퍼미션이 필요(기존 키에 퍼미션 없으면 403). 새 키 기본 퍼미션에 admin 포함.
- OIDC 기반 admin 검증 훅 추가(`FLAMEHAVEN_IAM_PROVIDER=oidc`, `FLAMEHAVEN_OIDC_*`).
- 민감 메타데이터 암호화를 위한 `FLAMEHAVEN_ENC_KEY`(32-byte base64, AES-256-GCM).

### Caching / Metrics
- Admin 캐시 관리: `/api/admin/cache/stats`, `/api/admin/cache/flush`.
- `/metrics`에 캐시/헬스 및 최근 60s/300s 요청/에러 요약 포함.
- 프런트 대시보드(cache/metrics/upload/admin) 연결.

### Full Details
See [CHANGELOG.md](CHANGELOG.md) for complete release notes.

---

## Upgrade Process

### Step 1: Pre-Upgrade Checklist

#### Backup Your Data (Recommended)
```bash
# Backup data directory (if you store API key DB locally)
tar -czf flamehaven_data_backup_$(date +%Y%m%d).tar.gz ./data
```

#### Check Current Version
```bash
pip show flamehaven-filesearch | grep Version
# Should show: Version: 1.0.0
```

#### Review Breaking Changes
**Good news**: v1.1.0 is fully backward compatible. No code changes required.

### Step 2: Upgrade Package

#### Option A: pip (Recommended)
```bash
# Upgrade to latest version
pip install -U flamehaven-filesearch[api]

# Verify installation
pip show flamehaven-filesearch | grep Version
# Should show: Version: 1.1.0
```

#### Option B: Git (Development)
```bash
cd Flamehaven-Filesearch
git pull origin main
git checkout v1.1.0
pip install -e .[dev,api]
```

#### Verify Dependencies
```bash
# Check critical dependencies
pip show fastapi | grep Version  # Should be >=0.121.1
pip show slowapi | grep Version  # Should be >=0.1.9
pip show cachetools | grep Version  # Should be >=5.3.0
```

### Step 3: Configuration (Optional)

#### New Environment Variables
v1.1.0 adds optional configuration:

```bash
# Logging mode (optional)
export ENVIRONMENT=production  # JSON logs (default)
# OR
export ENVIRONMENT=development  # Human-readable logs

# Server configuration (optional)
export HOST=0.0.0.0  # Server host (default)
export PORT=8000     # Server port (default)
export WORKERS=4     # Number of workers (production)
```

**Note**: Existing v1.0.0 configurations work without changes.

### Step 4: Start Service

#### Development/Testing
```bash
# Start with default settings
flamehaven-api

# Expected output:
# Starting FLAMEHAVEN FileSearch API v1.1.0 on 0.0.0.0:8000
# Features:
#   - Rate limiting: 10/min uploads, 100/min searches
#   - LRU caching with 1-hour TTL (1000 items)
#   - Prometheus metrics export
#   ...
```

#### Production (Systemd)
```bash
# Update systemd service (if using)
sudo systemctl restart flamehaven-api
sudo systemctl status flamehaven-api

# Check logs
sudo journalctl -u flamehaven-api -f
```

#### Docker
```bash
# Pull latest image
docker pull flamehaven/filesearch:1.1.0

# Restart container
docker-compose down
docker-compose up -d

# Or with docker run
docker stop flamehaven-filesearch
docker rm flamehaven-filesearch
docker run -d \
  --name flamehaven-filesearch \
  -e GEMINI_API_KEY="your-key" \
  -p 8000:8000 \
  -v flamehaven-data:/app/data \
  flamehaven/filesearch:1.1.0
```

### Step 5: Verify Upgrade

#### Health Check
```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "version": "1.1.0",
  "uptime_seconds": 10.5,
  "searcher_initialized": true,
  "system": {
    "cpu_percent": 15.2,
    "memory_percent": 45.3
  }
}
```

#### Test Caching
```bash
# First search (cache miss, ~2-3s)
time curl "http://localhost:8000/search?q=test+query"

# Second search (cache hit, <10ms)
time curl "http://localhost:8000/search?q=test+query"
```

#### Check Metrics
```bash
# View metrics
curl http://localhost:8000/metrics

# Should include cache statistics:
{
  "cache": {
    "search_cache": {
      "hits": 1,
      "misses": 1,
      "hit_rate_percent": 50.0
    }
  }
}
```

#### Prometheus Endpoint
```bash
# Access Prometheus metrics
curl http://localhost:8000/prometheus

# Should return metrics in text format:
# cache_hits_total{cache_type="search"} 1.0
# cache_misses_total{cache_type="search"} 1.0
# ...
```

---

## Migration Scenarios

### Scenario 1: Simple Upgrade (Most Users)
**Situation**: Running v1.0.0 in development/testing

**Steps**:
```bash
pip install -U flamehaven-filesearch[api]
flamehaven-api  # Just restart
```

**Time**: <2 minutes
**Downtime**: ~10 seconds (restart)

### Scenario 2: Production Deployment
**Situation**: v1.0.0 in production with systemd

**Steps**:
```bash
# 1. Backup
tar -czf flamehaven_backup_$(date +%Y%m%d).tar.gz ./data

# 2. Upgrade in maintenance window
sudo systemctl stop flamehaven-api
pip install -U flamehaven-filesearch[api]
sudo systemctl start flamehaven-api

# 3. Verify
curl http://localhost:8000/health | jq '.version'
# Should show: "1.1.0"

# 4. Monitor logs
sudo journalctl -u flamehaven-api -f --since "5 minutes ago"
```

**Time**: ~5 minutes
**Downtime**: ~30 seconds

### Scenario 3: Docker Deployment
**Situation**: v1.0.0 running in Docker

**Steps**:
```bash
# 1. Pull new image
docker pull flamehaven/filesearch:1.1.0

# 2. Update docker-compose.yml (optional)
# Change: image: flamehaven/filesearch:latest
# To:     image: flamehaven/filesearch:1.1.0

# 3. Recreate container
docker-compose down
docker-compose up -d

# 4. Verify
docker logs flamehaven_filesearch_1 | grep "v1.1.0"
```

**Time**: ~3 minutes
**Downtime**: ~20 seconds

### Scenario 4: Kubernetes Deployment
**Situation**: v1.0.0 in Kubernetes

**Steps**:
```bash
# 1. Update deployment manifest
# Change: image: flamehaven/filesearch:1.0.0
# To:     image: flamehaven/filesearch:1.1.0

# 2. Apply with rolling update (zero downtime)
kubectl set image deployment/flamehaven-filesearch \
  flamehaven=flamehaven/filesearch:1.1.0

# 3. Monitor rollout
kubectl rollout status deployment/flamehaven-filesearch

# 4. Verify
kubectl exec -it deployment/flamehaven-filesearch -- \
  curl localhost:8000/health | jq '.version'
```

**Time**: ~5 minutes
**Downtime**: 0 seconds (rolling update)

---

## Post-Upgrade Configuration

### Enable Prometheus Monitoring

#### Configure Prometheus Scraping
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'flamehaven-filesearch'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /prometheus
    scrape_interval: 15s
```

#### Grafana Dashboard (Optional)
1. Add Prometheus as data source
2. Import dashboard using metrics:
   - `http_requests_total`
   - `cache_hits_total`, `cache_misses_total`
   - `search_duration_seconds`
   - `system_cpu_usage_percent`

#### Set Up Alerts
```yaml
# alert.rules
groups:
  - name: flamehaven
    rules:
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
```

### Adjust Rate Limits (Optional)

If default rate limits are too restrictive:

**Option A: Environment Variables** (not yet supported, planned for v1.2.0)

**Option B: Reverse Proxy** (nginx)
```nginx
# nginx.conf
limit_req_zone $binary_remote_addr zone=uploads:10m rate=20r/m;
limit_req_zone $binary_remote_addr zone=searches:10m rate=200r/m;

location /api/upload {
    limit_req zone=uploads burst=5;
}

location /api/search {
    limit_req zone=searches burst=20;
}
```

### Enable Structured Logging

For production, use JSON logs for log aggregation:

```bash
# Production (default)
export ENVIRONMENT=production
flamehaven-api

# Logs will be JSON format:
# {"timestamp":"2025-11-13T12:00:00Z","level":"INFO","message":"..."}
```

For development, use readable logs:

```bash
# Development
export ENVIRONMENT=development
flamehaven-api

# Logs will be human-readable:
# 2025-11-13 12:00:00 - INFO - File uploaded successfully
```

---

## Troubleshooting

### Issue 1: Import Error After Upgrade
**Symptom**: `ImportError: cannot import name 'XXX' from 'flamehaven_filesearch'`

**Cause**: Cached bytecode from v1.0.0

**Solution**:
```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name '*.pyc' -delete

# Reinstall
pip uninstall flamehaven-filesearch
pip install flamehaven-filesearch[api]==1.1.0
```

### Issue 2: Rate Limiting Too Restrictive
**Symptom**: HTTP 429 responses during normal usage

**Cause**: Default rate limits may be too low for your use case

**Solution**:
```bash
# Option 1: Use reverse proxy (nginx) with higher limits
# See "Adjust Rate Limits" section above

# Option 2: Wait for v1.2.0 with configurable rate limits
# Coming Q1 2025

# Option 3: For development, restart API frequently
# Limits reset on restart
```

### Issue 3: Cache Not Working
**Symptom**: All searches still take 2-3 seconds

**Cause**: Different query parameters prevent cache hits

**Solution**:
```bash
# Cache key includes: query + store_name + model + max_tokens + temperature
# Ensure consistent parameters:

# This will NOT hit cache (different model):
curl "http://localhost:8000/search?q=test&model=gemini-pro"
curl "http://localhost:8000/search?q=test&model=gemini-flash"

# This WILL hit cache (same parameters):
curl "http://localhost:8000/search?q=test"
curl "http://localhost:8000/search?q=test"  # Cache hit!
```

### Issue 4: Metrics Not Showing Up
**Symptom**: `/prometheus` endpoint returns empty or minimal metrics

**Cause**: No traffic since restart

**Solution**:
```bash
# Generate some traffic
curl -X POST "http://localhost:8000/api/upload/single" -F "file=@test.pdf"
curl "http://localhost:8000/search?q=test"

# Now check metrics
curl http://localhost:8000/prometheus | grep -E '(http_requests|cache)'
```

### Issue 5: Permission Denied on Data Directory
**Symptom**: `PermissionError: [Errno 13] Permission denied: './data/...'`

**Cause**: Data directory permissions changed or running as different user

**Solution**:
```bash
# Check ownership
ls -ld ./data

# Fix ownership (replace 'username' with your user)
sudo chown -R username:username ./data

# Or for Docker
sudo chown -R 1000:1000 ./data
```

---

## Rollback Procedure

If you encounter issues with v1.1.0, you can roll back to v1.0.0:

### Step 1: Stop Service
```bash
# Systemd
sudo systemctl stop flamehaven-api

# Docker
docker-compose down

# Or kill process
pkill -f flamehaven-api
```

### Step 2: Downgrade Package
```bash
# Install v1.0.0
pip install flamehaven-filesearch[api]==1.0.0

# Verify
pip show flamehaven-filesearch | grep Version
# Should show: Version: 1.0.0
```

### Step 3: Restore Data (if needed)
```bash
# Only if data corruption occurred (unlikely)
rm -rf ./data
tar -xzf flamehaven_data_backup_$(date +%Y%m%d).tar.gz
```

### Step 4: Start Service
```bash
flamehaven-api
```

**Note**: Data created in v1.1.0 is fully compatible with v1.0.0. No data migration needed.

---

## FAQ

### Q: Do I need to change my code?
**A**: No. v1.1.0 is fully backward compatible. Existing code will work without changes.

### Q: Will my uploaded files still work?
**A**: Yes. Data format is unchanged. All files uploaded in v1.0.0 will work in v1.1.0.

### Q: Can I upgrade without downtime?
**A**: Yes, if using Kubernetes with rolling updates. Otherwise, ~10-30 seconds downtime during restart.

### Q: Do I need to clear the cache manually?
**A**: No. Cache is in-memory and resets on service restart. TTL is 1 hour.

### Q: How do I disable caching?
**A**: Not configurable in v1.1.0. Planned for v1.2.0. Cache is beneficial for 99% of use cases.

### Q: Are there any performance regressions?
**A**: No. Performance is strictly better in v1.1.0 (cache hits are 99% faster).

### Q: Do I need to update my Dockerfile?
**A**: Only if pinning to specific version. Change `FROM flamehaven/filesearch:1.0.0` to `:1.1.0`.

### Q: What happens to rate limits on service restart?
**A**: Rate limits reset on restart (in-memory state). For persistent rate limiting, use Redis (planned for v1.2.0).

### Q: How do I monitor cache hit rate?
**A**: Use `/metrics` endpoint or Prometheus:
```bash
curl http://localhost:8000/metrics | jq '.cache.search_cache.hit_rate_percent'
# Or Prometheus
curl http://localhost:8000/prometheus | grep cache_hits_total
```

---

## Support

**Upgrade Issues**: [Open an issue](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)
**Questions**: [GitHub Discussions](https://github.com/flamehaven01/Flamehaven-Filesearch/discussions)
**Security**: security@flamehaven.space
**General**: info@flamehaven.space

---

## Next Steps

After upgrading to v1.1.0:
1. ✅ Set up Prometheus monitoring
2. ✅ Configure structured logging for production
3. ✅ Review [SECURITY.md](SECURITY.md) for best practices
4. ✅ Monitor cache hit rate and adjust usage patterns
5. ✅ Subscribe to release notifications for v1.2.0

---

**Last Updated**: 2025-11-13
**Document Version**: 1.0.0 (v1.0.0 -> v1.1.0 migration)

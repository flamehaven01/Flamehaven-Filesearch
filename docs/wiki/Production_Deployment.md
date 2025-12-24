# Production Deployment Guide

This playbook describes how to run Flamehaven FileSearch in a secured,
observable environment. Adjust to match your infrastructure.

---

## 1. Reference Architecture

```
[Client] -> [Reverse Proxy / WAF] -> [Flamehaven API (Uvicorn/Gunicorn)] -> [Document Storage]
                                                      |
                                                      +--> [Prometheus/Grafana]
```

- Reverse proxy terminates TLS (nginx, Traefik, Cloudflare).
- API runs as non-root user.
- Persistent storage mounted at `/data/documents`.

---

## 2. Docker Deployment

```bash
docker build -t flamehaven-filesearch:1.1.0 .

docker run -d --name flamehaven \
  -p 8000:8000 \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e DEFAULT_MODEL=gemini-2.5-flash \
  -e ENVIRONMENT=production \
  -v /srv/flamehaven/data:/app/data \
  flamehaven-filesearch:1.1.0
```

**Tips**

- Use `--restart unless-stopped`.
- Set `LOG_LEVEL=info` to reduce noise.
- On Kubernetes, add readiness probe hitting `/health`.

---

## 3. Systemd Service (Bare Metal)

`/etc/systemd/system/flamehaven.service`

```ini
[Unit]
Description=Flamehaven FileSearch API
After=network.target

[Service]
Environment="GEMINI_API_KEY=/etc/secrets/gemini.key"
Environment="ENVIRONMENT=production"
WorkingDirectory=/opt/flamehaven
ExecStart=/opt/flamehaven/.venv/bin/flamehaven-api
User=flamehaven
Group=flamehaven
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable with `systemctl enable --now flamehaven`.

---

## 4. Reverse Proxy & TLS

Example nginx snippet:

```nginx
server {
    listen 443 ssl;
    server_name search.example.com;

    ssl_certificate /etc/letsencrypt/live/search/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/search/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }
}
```

Enable HTTP/2 and OCSP stapling for best performance.

---

## 5. Scaling Strategy

| Scenario | Recommendation |
|----------|---------------|
| < 50 req/min | Single instance (Uvicorn, 2 workers) |
| 50–500 req/min | Gunicorn with `--workers $(CPU*2)` + `--worker-class uvicorn.workers.UvicornWorker` |
| > 500 req/min | Horizontal scaling behind load balancer; externalize cache (Redis) |

Set RATE limits more aggressively when running multiple replicas to avoid
exhausting Gemini quota.

---

## 6. Observability

1. **Metrics** – Scrape `/prometheus` (requires `FLAMEHAVEN_METRICS_ENABLED=1` and admin access unless internal). Example configuration for Prometheus:
   ```yaml
   - job_name: flamehaven
     scrape_interval: 15s
     metrics_path: /prometheus
     static_configs:
       - targets: ['flamehaven:8000']
   ```
2. **Logging** – Send STDOUT to Loki/ELK. JSON logs contain
   `service`, `version`, `request_id`, `environment`.
3. **Tracing** – Propagate `X-Request-ID` through reverse proxy to correlate
   across services.

---

## 7. Backups & Disaster Recovery

- **Documents**: If using local storage, back up `/srv/flamehaven/data`. Consider
  object storage (S3, GCS) for durability.
- **Configuration**: Store `.env.production` in secure secret manager.
- **Rotation**: Regenerate Gemini API key every 90 days. Update secrets via
  CI/CD pipeline.

---

## 8. Security Hardening

- Run container as non-root (`USER 1000`).
- Enable `ufw`/`iptables` to allow ingress only on 80/443.
- Add WAF rules for `/api/upload/*`.
- Periodically run `gitleaks` and `trufflehog` (already configured in CI).
- Keep dependencies up to date (`pip install -U flamehaven-filesearch`).

---

## 9. Production Checklist

- [ ] TLS certificate valid and auto-renewed.
- [ ] Rate limits tuned for workload.
- [ ] Prometheus scrape working; alerts configured for `errors_total` and
  `rate_limit_exceeded`.
- [ ] Backups tested.
- [ ] Runbook stored with the operations team.

With these steps you can safely run Flamehaven FileSearch in production for
internal knowledge bases or customer-facing search experiences.

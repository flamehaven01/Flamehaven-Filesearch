# FLAMEHAVEN FileSearch v1.2.0 Deployment Guide

## Quick Start (5 Minutes)

### Option 1: Local Development

```bash
# 1. Install dependencies
pip install flamehaven-filesearch[api]

# 2. Set environment variables
export GEMINI_API_KEY="your_gemini_api_key"
export FLAMEHAVEN_ADMIN_KEY="your_secure_admin_key"
export ENVIRONMENT="development"

# 3. Start API server
python -m flamehaven_filesearch.api

# 4. Access dashboard
# Open http://localhost:8000/admin/dashboard

# 5. Generate first API key
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_secure_admin_key" \
  -H "Content-Type: application/json" \
  -d '{"name":"Dev Key","permissions":["upload","search"]}'
```

### Option 2: Docker (Recommended for Production)

```bash
# 1. Build image
docker build -t flamehaven-filesearch:1.2.0 .

# 2. Run container
docker run \
  -e GEMINI_API_KEY="your_gemini_key" \
  -e FLAMEHAVEN_ADMIN_KEY="your_admin_key" \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  flamehaven-filesearch:1.2.0

# 3. Access at http://localhost:8000
```

---

## Detailed Installation

### Prerequisites
- Python 3.8+ or Docker
- Google Gemini API key
- (Optional) Redis 6.0+ for distributed caching

### Step 1: Install Package

#### Pip Installation
```bash
# Minimal installation (core functionality)
pip install flamehaven-filesearch

# Full installation with API server
pip install flamehaven-filesearch[api]

# With Redis support
pip install flamehaven-filesearch[api,redis]

# Complete installation (development + testing)
pip install flamehaven-filesearch[all]
```

#### Source Installation
```bash
git clone https://github.com/flamehaven01/Flamehaven-Filesearch.git
cd Flamehaven-Filesearch
pip install -e ".[api]"
```

### Step 2: Configure Environment

#### Required Variables
```bash
export GEMINI_API_KEY="<your_google_gemini_api_key>"
export FLAMEHAVEN_ADMIN_KEY="<your_secure_admin_password>"
```

#### Optional Variables
```bash
# Server Configuration
export HOST="0.0.0.0"              # Default: 127.0.0.1
export PORT="8000"                  # Default: 8000
export ENVIRONMENT="production"     # Default: development

# Database Location
export FLAMEHAVEN_API_KEYS_DB="/data/api_keys.db"

# Redis Configuration (for caching)
export REDIS_HOST="localhost"       # Default: localhost
export REDIS_PORT="6379"            # Default: 6379
export REDIS_PASSWORD="<password>"  # Optional
export REDIS_DB="0"                 # Default: 0

# API Configuration
export MAX_FILE_SIZE_MB="50"        # Default: 50
export CORS_ORIGINS="*"             # Default: *
```

### Step 3: Initialize Database

The API key database is created automatically on first run. To pre-initialize:

```bash
python -c "from flamehaven_filesearch.auth import get_key_manager; mgr = get_key_manager(); print('Database initialized')"
```

### Step 4: Create Admin API Key

```bash
# Via curl
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: $FLAMEHAVEN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "permissions": ["upload", "search", "stores", "delete"],
    "rate_limit_per_minute": 100
  }'

# Response will include the plain key (SAVE THIS SAFELY)
```

### Step 5: Test Installation

```bash
# Test health endpoint (public, no auth required)
curl http://localhost:8000/health

# Test dashboard (public)
curl http://localhost:8000/admin/dashboard

# Test authenticated endpoint with your API key
curl -X GET http://localhost:8000/api/stores \
  -H "Authorization: Bearer your_api_key_here"
```

---

## Docker Deployment

### Single Container

```bash
# Build
docker build -t flamehaven-filesearch:1.2.0 .

# Run
docker run \
  --name flamehaven-api \
  -d \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e FLAMEHAVEN_ADMIN_KEY="$FLAMEHAVEN_ADMIN_KEY" \
  -e ENVIRONMENT="production" \
  -p 8000:8000 \
  -v flamehaven-data:/app/data \
  flamehaven-filesearch:1.2.0

# View logs
docker logs -f flamehaven-api

# Stop container
docker stop flamehaven-api
```

### With Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # API Server
  api:
    build: .
    container_name: flamehaven-api
    environment:
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      FLAMEHAVEN_ADMIN_KEY: ${FLAMEHAVEN_ADMIN_KEY}
      ENVIRONMENT: production
      REDIS_HOST: redis
      REDIS_PORT: 6379
    ports:
      - "8000:8000"
    volumes:
      - flamehaven-data:/app/data
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s

  # Redis Cache (optional)
  redis:
    image: redis:7-alpine
    container_name: flamehaven-redis
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  flamehaven-data:
  redis-data:
```

Deploy with:
```bash
# Create .env file
cat > .env << EOF
GEMINI_API_KEY=your_key_here
FLAMEHAVEN_ADMIN_KEY=your_admin_key_here
EOF

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl create namespace flamehaven
```

### 2. Create Secrets

```bash
# Create secret for API keys
kubectl create secret generic flamehaven-secrets \
  --from-literal=GEMINI_API_KEY="your_gemini_key" \
  --from-literal=FLAMEHAVEN_ADMIN_KEY="your_admin_key" \
  -n flamehaven
```

### 3. Create ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flamehaven-config
  namespace: flamehaven
data:
  ENVIRONMENT: "production"
  REDIS_HOST: "redis.flamehaven.svc.cluster.local"
  REDIS_PORT: "6379"
  MAX_FILE_SIZE_MB: "50"
```

Apply:
```bash
kubectl apply -f configmap.yaml
```

### 4. Deploy API Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flamehaven-api
  namespace: flamehaven
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: flamehaven-api
  template:
    metadata:
      labels:
        app: flamehaven-api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/prometheus"
    spec:
      serviceAccountName: flamehaven
      containers:
      - name: api
        image: flamehaven-filesearch:1.2.0
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: flamehaven-config
              key: ENVIRONMENT
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: flamehaven-secrets
              key: GEMINI_API_KEY
        - name: FLAMEHAVEN_ADMIN_KEY
          valueFrom:
            secretKeyRef:
              name: flamehaven-secrets
              key: FLAMEHAVEN_ADMIN_KEY
        - name: REDIS_HOST
          valueFrom:
            configMapKeyRef:
              name: flamehaven-config
              key: REDIS_HOST
        - name: REDIS_PORT
          valueFrom:
            configMapKeyRef:
              name: flamehaven-config
              key: REDIS_PORT
        - name: MAX_FILE_SIZE_MB
          valueFrom:
            configMapKeyRef:
              name: flamehaven-config
              key: MAX_FILE_SIZE_MB
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 15
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: flamehaven-data

---
apiVersion: v1
kind: Service
metadata:
  name: flamehaven-api
  namespace: flamehaven
spec:
  selector:
    app: flamehaven-api
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
    name: http

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: flamehaven-data
  namespace: flamehaven
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

Deploy:
```bash
kubectl apply -f deployment.yaml
```

### 5. Deploy Redis (Optional)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: flamehaven
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
          - redis-server
          - "--appendonly"
          - "yes"
        ports:
        - containerPort: 6379
          name: redis
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
        volumeMounts:
        - name: redis-data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 5Gi

---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: flamehaven
spec:
  clusterIP: None
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

---

## Monitoring & Operations

### Health Checks

```bash
# API Health
curl http://localhost:8000/health

# Prometheus Metrics
curl http://localhost:8000/prometheus

# Dashboard
curl http://localhost:8000/admin/dashboard
```

### Monitoring Integration

#### Prometheus
```yaml
scrape_configs:
  - job_name: 'flamehaven'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/prometheus'
    scrape_interval: 30s
```

#### Grafana Dashboard
Import dashboard from: [Grafana Dashboard Hub](https://grafana.com)

Search for: "FLAMEHAVEN FileSearch"

### Logging

View logs:
```bash
# Docker
docker logs flamehaven-api

# Docker Compose
docker-compose logs -f api

# Kubernetes
kubectl logs -n flamehaven deployment/flamehaven-api -f
```

Logs are in JSON format for easy parsing:
```json
{
  "timestamp": "2025-11-16T10:30:45.123Z",
  "level": "INFO",
  "logger": "flamehaven_filesearch.api",
  "message": "Search completed successfully",
  "request_id": "req_abc123...",
  "service": "flamehaven-filesearch",
  "version": "1.2.0"
}
```

---

## Scaling & Performance

### Horizontal Scaling

1. **Stateless Design:** API servers are stateless, scale freely
2. **Redis Cache:** Shared cache across multiple instances
3. **Load Balancing:** Use reverse proxy (nginx, Kubernetes service)

### Recommended Configuration

**Small Deployment (< 1000 req/day):**
- 1 API instance
- Optional Redis cache
- 2GB RAM

**Medium Deployment (1000-10000 req/day):**
- 2-3 API instances
- Redis cache (required)
- 4GB RAM per instance

**Large Deployment (10000+ req/day):**
- 5+ API instances
- Redis cluster
- 8GB RAM per instance
- Dedicated database server

---

## Backup & Recovery

### Backup Strategy

```bash
# Backup API keys database
docker exec flamehaven-api \
  tar czf /app/data/api_keys_backup.tar.gz \
  /app/data/api_keys.db

# Backup from host
cp /path/to/data/api_keys.db /backup/api_keys.db.backup
```

### Restore

```bash
# Restore from backup
cp /backup/api_keys.db.backup /path/to/data/api_keys.db
docker restart flamehaven-api
```

---

## Troubleshooting

### Common Issues

**Issue: 401 Unauthorized on all requests**
```
Solution: Check FLAMEHAVEN_ADMIN_KEY is set correctly
         Verify API key is valid and not expired
         Check Authorization header format: "Bearer sk_live_..."
```

**Issue: Redis connection refused**
```
Solution: Ensure Redis is running: redis-cli ping
         Check REDIS_HOST and REDIS_PORT are correct
         Add -e REDIS_HOST=redis to docker run
```

**Issue: High memory usage**
```
Solution: Configure Redis eviction policy: maxmemory-policy
         Reduce cache TTL in environment variables
         Monitor with: curl http://localhost:8000/prometheus | grep cache
```

**Issue: Slow searches**
```
Solution: Check if cache is working (cache_hits_total metric)
         Verify Gemini API is responsive
         Check network latency to Redis
```

---

## Upgrade Path

### From v1.1.0 to v1.2.0

```bash
# 1. Backup current data
docker exec flamehaven-api cp -r /app/data /app/data.backup

# 2. Update image
docker pull flamehaven-filesearch:1.2.0

# 3. Update container
docker-compose up -d --no-deps --build api

# 4. Verify
curl http://localhost:8000/health

# 5. Generate API keys
# See "Step 4: Create Admin API Key" above

# 6. Update application code to use Bearer tokens
```

---

## Support

- **Documentation:** README.md, API docs at /docs
- **Issues:** GitHub Issues
- **Email:** support@flamehaven.space


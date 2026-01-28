# MarketScout Deployment Guide

This guide covers deploying MarketScout to various environments.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [AWS Deployment](#aws-deployment)
4. [Configuration](#configuration)

---

## Local Development

### Prerequisites

- Python 3.11+
- C++ compiler (for C++ engine, optional)
- PostgreSQL 15+ with TimescaleDB (optional)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd marketscout

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp env.example .env

# Edit configuration (optional)
# nano .env

# Run in simulation mode
python main.py
```

### Access Points

- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Metrics**: http://localhost:8000/metrics

### Default Credentials

- Username: `admin`
- Password: `Changeme123`

---

## Docker Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Basic Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### With C++ Engine (High Performance)

```bash
# Start with C++ engine profile
docker-compose --profile cpp up -d
```

### With Monitoring Stack

```bash
# Start with Prometheus and Grafana
docker-compose --profile monitoring up -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| app | 8000 | Main application |
| db | 5432 | PostgreSQL/TimescaleDB |
| redis | 6379 | Cache (optional) |
| cpp-engine | 5555 | C++ engine (optional) |
| prometheus | 9090 | Metrics (optional) |
| grafana | 3000 | Dashboards (optional) |

---

## AWS Deployment

### Prerequisites

- AWS CLI configured
- Appropriate IAM permissions
- Docker installed locally

### Infrastructure Setup

```bash
# Run infrastructure setup script
chmod +x scripts/setup_aws_infrastructure.sh
./scripts/setup_aws_infrastructure.sh dev
```

This creates:
- ECS Cluster
- ECR Repositories
- CloudWatch Log Groups
- Secrets Manager entries
- IAM Roles

### Deploy Application

```bash
# Deploy to development
chmod +x scripts/deploy_aws.sh
./scripts/deploy_aws.sh dev

# Deploy to production
./scripts/deploy_aws.sh prod
```

### Manual AWS Setup

If you prefer manual setup or need customization:

#### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name marketscout-python
aws ecr create-repository --repository-name marketscout-cpp
```

#### 2. Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build images
docker build -t marketscout-python -f docker/Dockerfile.python .
docker build -t marketscout-cpp -f docker/Dockerfile.cpp .

# Tag and push
docker tag marketscout-python:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/marketscout-python:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/marketscout-python:latest
```

#### 3. Create RDS Instance (Optional)

```bash
aws rds create-db-instance \
    --db-instance-identifier marketscout-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username postgres \
    --master-user-password <password> \
    --allocated-storage 20
```

#### 4. Create ECS Service

Use the AWS Console or CloudFormation to create:
- ECS Task Definition
- ECS Service
- Application Load Balancer
- Target Groups

### Environment Variables for AWS

Set these in Secrets Manager or ECS Task Definition:

```
MODE=python
DATABASE_URL=postgresql://user:pass@host:5432/arbitrage
JWT_SECRET=<secure-random-string>
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODE` | `simulation` | Operation mode: `simulation`, `python`, `cpp` |
| `WEB_HOST` | `0.0.0.0` | Web server host |
| `WEB_PORT` | `8000` | Web server port |
| `DATABASE_URL` | - | PostgreSQL connection string |
| `JWT_SECRET` | - | Secret key for JWT tokens |
| `JWT_EXPIRY_HOURS` | `24` | Token expiration time |

### Trading Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_PROFIT_THRESHOLD` | `0.01` | Minimum profit % for alerts |
| `ENABLE_TRIANGULAR_ARBITRAGE` | `true` | Enable triangular detection |
| `TRADING_PAIRS` | `BTC/USDT,...` | Comma-separated pairs |

### Notifications

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server for email |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL |

---

## Health Checks

### Endpoints

- `GET /api/health` - Basic health check
- `GET /metrics` - Prometheus metrics

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## Monitoring

### Prometheus Metrics

Available at `/metrics`:
- `price_updates_total` - Price updates by exchange
- `opportunities_detected_total` - Opportunities by type
- `websocket_connections` - Active WebSocket clients
- `tick_storage_total` - Stored tick count

### Grafana Dashboard

Import the dashboard from `engine_metrics.py`:

```python
from engine_metrics import get_grafana_dashboard_json
dashboard = get_grafana_dashboard_json()
```

---

## Troubleshooting

### Common Issues

**1. WebSocket connection failed**
- Check if port 8000 is accessible
- Verify CORS settings for your domain

**2. Database connection failed**
- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL is running and accessible

**3. C++ engine not starting**
- Check if Boost libraries are installed
- Verify OpenSSL is available

### Logs

```bash
# Docker logs
docker-compose logs -f app

# AWS ECS logs
aws logs tail /ecs/marketscout-dev --follow
```

---

## Security Checklist

- [ ] Change default admin password
- [ ] Set strong JWT_SECRET
- [ ] Enable HTTPS in production
- [ ] Configure CORS for your domain
- [ ] Use AWS Secrets Manager for credentials
- [ ] Enable database encryption at rest
- [ ] Set up VPC security groups
- [ ] Enable CloudWatch alarms

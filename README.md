# SYS-DESUGN — AI Log Analyzer (AIOps MVP)

An end-to-end **AI-powered log analysis and anomaly detection** platform built for production-grade observability.

## 📦 Repository Structure

```
ai-log-analyzer/
├── backend/
│   ├── ingestion/       # FastAPI log ingestion service → Kafka
│   ├── processing/      # Kafka consumer, normalizer, feature windowing → ES
│   ├── ai_engine/       # Anomaly detection, RCA, clustering
│   ├── alerts/          # Alert dispatcher (Slack + fallback logging)
│   └── api/             # REST API (logs, anomalies, NL query, stats)
├── frontend/
│   └── dashboard/       # React + Vite + Tailwind SPA (4 pages)
├── infra/
│   ├── docker-compose.yml
│   ├── k8s/             # Kubernetes manifests
│   └── helm/            # Helm chart values
├── tests/               # Pytest unit tests
├── scripts/             # Test data generator, ES index creator
└── docs/                # Architecture docs
```

## 🚀 Quick Start (Docker Compose)

```bash
cd ai-log-analyzer/infra
docker compose up -d
```

| Service        | URL                        |
|----------------|----------------------------|
| Frontend       | http://localhost:3000       |
| API            | http://localhost:8000/docs  |
| Ingestion      | http://localhost:8001/docs  |
| Kibana         | http://localhost:5601       |
| Elasticsearch  | http://localhost:9200       |

## 🔄 Data Flow

1. **Ingest** — POST logs to `http://localhost:8001/ingest` (single or batch)
2. **Process** — Kafka consumer normalizes logs → Elasticsearch `logs` index
3. **Feature Windows** — 60s tumbling windows compute per-service error counts
4. **Detect** — AI Engine polls every 30s, flags anomalies above threshold
5. **Alert** — Alert service sends Slack webhooks (or logs to stdout)
6. **Explore** — Frontend dashboard + API provides search, NL query, and stats

## 🧪 Send Test Logs

```bash
# Install requests
pip install requests

# Normal traffic
python scripts/send_test_logs.py --mode normal --count 50

# Trigger an anomaly burst
python scripts/send_test_logs.py --mode anomaly --service payment-service --count 25

# Continuous simulation
python scripts/send_test_logs.py --mode continuous
```

## ✅ Run Tests

```bash
cd ai-log-analyzer
pip install pytest pytest-mock fastapi[testing] httpx pydantic==1.10.15 python-dateutil
python -m pytest tests/ -v
```

## ⚙️ Configuration

| Variable                  | Default                    | Service       |
|---------------------------|----------------------------|---------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092`              | ingestion, processing |
| `ELASTICSEARCH_URL`       | `http://elasticsearch:9200`| all backends  |
| `ANOMALY_ERROR_THRESHOLD` | `10`                       | ai_engine     |
| `POLL_INTERVAL_SECONDS`   | `30`                       | ai_engine, alerts |
| `SLACK_WEBHOOK_URL`       | *(empty = log only)*       | alerts        |

## 📐 Architecture

See [`docs/architecture.md`](ai-log-analyzer/docs/architecture.md) for the full component diagram.
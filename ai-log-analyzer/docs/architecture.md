# Architecture Overview

## System Components

```
[Log Sources] → [Ingestion Service] → [Kafka: raw-logs] → [Processing Service]
                                                                    ↓
                                                           [Elasticsearch: logs]
                                                           [Elasticsearch: log-features]
                                                                    ↓
                                                           [AI Engine Service]
                                                                    ↓
                                                           [Elasticsearch: anomalies]
                                                                    ↓
                                                           [Alert Service] → [Slack / Log]
                                                                    
[Frontend Dashboard] ← [API Service] ← [Elasticsearch]
```

## Data Flow
1. Log sources POST to Ingestion Service `/ingest`
2. Ingestion validates and publishes to Kafka `raw-logs` topic
3. Processing Service consumes, normalizes, stores in ES `logs` index
4. Processing computes 60s rolling feature windows stored in `log-features`
5. AI Engine polls `log-features` every 30s, detects anomalies via threshold logic
6. Detected anomalies stored in `anomalies` index with RCA explanation
7. Alert Service polls `anomalies`, sends Slack notifications
8. Frontend queries API Service which reads from Elasticsearch

## Indices
- `logs` - normalized log entries
- `log-features` - per-service per-window error/warn/info counts  
- `anomalies` - detected anomalies with severity, RCA, notification status

import os
import time
import logging
import schedule
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests
from elasticsearch import Elasticsearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("alerts")

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))


def get_es_client() -> Elasticsearch:
    for attempt in range(10):
        try:
            es = Elasticsearch(ES_URL)
            if es.ping():
                logger.info("Connected to Elasticsearch at %s", ES_URL)
                return es
        except Exception as exc:
            logger.warning("ES connection attempt %d: %s", attempt + 1, exc)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Cannot connect to Elasticsearch")


def fetch_unnotified_anomalies(es: Elasticsearch) -> List[Dict[str, Any]]:
    try:
        resp = es.search(
            index="anomalies",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"status": "open"}},
                            {"term": {"notified": False}},
                        ]
                    }
                },
                "size": 100,
            },
        )
        return [(hit["_id"], hit["_source"]) for hit in resp["hits"]["hits"]]
    except Exception as exc:
        logger.error("Failed to fetch anomalies: %s", exc)
        return []


def send_slack_alert(webhook_url: str, anomaly: Dict[str, Any]) -> bool:
    service = anomaly.get("service", "unknown")
    severity = anomaly.get("severity", "unknown")
    error_count = anomaly.get("error_count", 0)
    rca = anomaly.get("rca", "")
    detected_at = anomaly.get("detected_at", "")

    color_map = {"critical": "#FF0000", "high": "#FF8C00", "medium": "#FFD700"}
    color = color_map.get(severity, "#808080")

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"🚨 AIOps Alert: Anomaly in {service}",
                "fields": [
                    {"title": "Service", "value": service, "short": True},
                    {"title": "Severity", "value": severity.upper(), "short": True},
                    {"title": "Error Count", "value": str(error_count), "short": True},
                    {"title": "Detected At", "value": detected_at, "short": True},
                    {"title": "RCA", "value": rca, "short": False},
                ],
                "footer": "AI Log Analyzer",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ]
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Slack webhook failed: %s", exc)
        return False


def mark_notified(es: Elasticsearch, anomaly_id: str):
    try:
        es.update(
            index="anomalies",
            id=anomaly_id,
            body={"doc": {"notified": True, "notified_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as exc:
        logger.error("Failed to mark anomaly %s as notified: %s", anomaly_id, exc)


def process_alerts(es: Elasticsearch):
    logger.info("Checking for unnotified anomalies")
    items = fetch_unnotified_anomalies(es)
    if not items:
        logger.debug("No unnotified anomalies")
        return

    for anomaly_id, anomaly in items:
        service = anomaly.get("service", "unknown")
        severity = anomaly.get("severity", "unknown")
        error_count = anomaly.get("error_count", 0)

        if SLACK_WEBHOOK_URL:
            success = send_slack_alert(SLACK_WEBHOOK_URL, anomaly)
            if success:
                logger.info("Slack alert sent for anomaly %s (%s/%s)", anomaly_id, service, severity)
        else:
            logger.warning(
                "[ALERT] Anomaly %s | service=%s | severity=%s | error_count=%d | rca=%s",
                anomaly_id,
                service,
                severity,
                error_count,
                anomaly.get("rca", ""),
            )
        mark_notified(es, anomaly_id)


def main():
    es = get_es_client()
    schedule.every(POLL_INTERVAL_SECONDS).seconds.do(process_alerts, es=es)
    logger.info("Alert service started, polling every %ds", POLL_INTERVAL_SECONDS)
    process_alerts(es)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()

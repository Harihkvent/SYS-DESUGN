import os
import time
import uuid
import hashlib
import logging
import schedule
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from elasticsearch import Elasticsearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ai_engine")

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
ANOMALY_ERROR_THRESHOLD = int(os.getenv("ANOMALY_ERROR_THRESHOLD", "10"))
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


def ensure_anomalies_index(es: Elasticsearch):
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "service": {"type": "keyword"},
                "window_start": {"type": "date"},
                "error_count": {"type": "integer"},
                "threshold": {"type": "integer"},
                "severity": {"type": "keyword"},
                "status": {"type": "keyword"},
                "notified": {"type": "boolean"},
                "detected_at": {"type": "date"},
                "rca": {"type": "text"},
                "cluster": {"type": "keyword"},
            }
        }
    }
    if not es.indices.exists(index="anomalies"):
        es.indices.create(index="anomalies", body=mapping)
        logger.info("Created index: anomalies")


class EmbeddingGenerator:
    """Generates embeddings. Uses sentence-transformers if available, else hash mock."""

    def __init__(self):
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Using sentence-transformers for embeddings")
        except ImportError:
            logger.info("sentence-transformers not available; using hash-based mock embeddings")

    def encode(self, texts: List[str]) -> List[List[float]]:
        if self._model is not None:
            return self._model.encode(texts).tolist()
        # Deterministic hash-based mock: 64-dim float vector
        # SHA-256 yields 32 bytes; concatenate two hashes for 64 dims
        result = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            digest2 = hashlib.sha256((text + "_2").encode()).digest()
            raw = digest + digest2  # 64 bytes
            vec = [(b / 255.0) * 2 - 1 for b in raw]
            result.append(vec)
        return result


class Clusterer:
    """Groups anomalies by (service, error_pattern) key."""

    def cluster(self, anomalies: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for a in anomalies:
            key = f"{a.get('service', 'unknown')}:high_error_rate"
            groups.setdefault(key, []).append(a)
        return groups


class RCAAgent:
    """Root Cause Analysis stub - returns template explanation for MVP."""

    def explain(self, anomaly: Dict[str, Any]) -> str:
        service = anomaly.get("service", "unknown")
        error_count = anomaly.get("error_count", 0)
        threshold = anomaly.get("threshold", ANOMALY_ERROR_THRESHOLD)
        window_start = anomaly.get("window_start", "unknown time")
        return (
            f"Anomaly detected in service '{service}': {error_count} errors in 60s window "
            f"starting {window_start} (threshold: {threshold}). "
            f"Possible causes: (1) upstream dependency failure, "
            f"(2) resource exhaustion (CPU/memory), "
            f"(3) recent deployment introduced regression. "
            f"Recommended actions: check service logs, review recent deployments, inspect dependency health."
        )


class AnomalyDetector:
    def __init__(self, es: Elasticsearch, threshold: int = ANOMALY_ERROR_THRESHOLD):
        self.es = es
        self.threshold = threshold
        self.rca = RCAAgent()
        self.clusterer = Clusterer()

    def fetch_recent_features(self) -> List[Dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        try:
            resp = self.es.search(
                index="log-features",
                body={
                    "query": {"range": {"window_start": {"gte": since}}},
                    "size": 500,
                },
            )
            return [hit["_source"] for hit in resp["hits"]["hits"]]
        except Exception as exc:
            logger.error("Failed to fetch features: %s", exc)
            return []

    def detect(self) -> List[Dict[str, Any]]:
        features = self.fetch_recent_features()
        anomalies = []
        for feat in features:
            error_count = feat.get("error_count", 0)
            if error_count > self.threshold:
                severity = "critical" if error_count > self.threshold * 3 else "high" if error_count > self.threshold * 2 else "medium"
                anomaly_id = str(uuid.uuid4())
                anomaly = {
                    "id": anomaly_id,
                    "service": feat.get("service", "unknown"),
                    "window_start": feat.get("window_start"),
                    "error_count": error_count,
                    "threshold": self.threshold,
                    "severity": severity,
                    "status": "open",
                    "notified": False,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
                anomaly["rca"] = self.rca.explain(anomaly)
                clusters = self.clusterer.cluster([anomaly])
                anomaly["cluster"] = list(clusters.keys())[0] if clusters else "unclustered"
                anomalies.append(anomaly)
        return anomalies

    def store_anomalies(self, anomalies: List[Dict[str, Any]]):
        for anomaly in anomalies:
            self.es.index(index="anomalies", id=anomaly["id"], body=anomaly)
            logger.info("Stored anomaly %s for service %s (severity=%s)", anomaly["id"], anomaly["service"], anomaly["severity"])


def run_detection(detector: AnomalyDetector):
    logger.info("Running anomaly detection cycle")
    try:
        anomalies = detector.detect()
        if anomalies:
            detector.store_anomalies(anomalies)
            logger.info("Detected and stored %d anomalies", len(anomalies))
        else:
            logger.debug("No anomalies detected")
    except Exception as exc:
        logger.error("Detection cycle error: %s", exc)


def main():
    es = get_es_client()
    ensure_anomalies_index(es)
    detector = AnomalyDetector(es, ANOMALY_ERROR_THRESHOLD)

    schedule.every(POLL_INTERVAL_SECONDS).seconds.do(run_detection, detector=detector)
    logger.info("AI Engine started, polling every %ds", POLL_INTERVAL_SECONDS)

    run_detection(detector)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()

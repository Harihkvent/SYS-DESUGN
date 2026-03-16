import os
import json
import uuid
import logging
import time
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any

from confluent_kafka import Consumer, KafkaError
from elasticsearch import Elasticsearch, helpers
from dateutil import parser as dateutil_parser

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("processing")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "raw-logs")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "processing-service")
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))


def get_es_client() -> Elasticsearch:
    for attempt in range(10):
        try:
            es = Elasticsearch(ES_URL)
            if es.ping():
                logger.info("Connected to Elasticsearch at %s", ES_URL)
                return es
        except Exception as exc:
            logger.warning("ES connection attempt %d failed: %s", attempt + 1, exc)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Cannot connect to Elasticsearch")


def ensure_indices(es: Elasticsearch):
    logs_mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "message": {"type": "text"},
                "level": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "received_at": {"type": "date"},
                "service": {"type": "keyword"},
                "host": {"type": "keyword"},
                "extra_fields": {"type": "object", "dynamic": True},
            }
        }
    }
    features_mapping = {
        "mappings": {
            "properties": {
                "window_start": {"type": "date"},
                "service": {"type": "keyword"},
                "error_count": {"type": "integer"},
                "warn_count": {"type": "integer"},
                "info_count": {"type": "integer"},
                "total_count": {"type": "integer"},
            }
        }
    }
    for index, mapping in [("logs", logs_mapping), ("log-features", features_mapping)]:
        if not es.indices.exists(index=index):
            es.indices.create(index=index, body=mapping)
            logger.info("Created index: %s", index)


class WindowAccumulator:
    """Accumulates per-service log level counts in 60s tumbling windows."""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        # key: (window_start_epoch, service) -> {error, warn, info, total}
        self._windows: Dict[tuple, Dict[str, int]] = defaultdict(lambda: {"error_count": 0, "warn_count": 0, "info_count": 0, "total_count": 0})

    def _window_key(self, ts: datetime, service: str) -> tuple:
        epoch = int(ts.timestamp())
        window_start = epoch - (epoch % self.window_seconds)
        return (window_start, service)

    def add(self, log: Dict[str, Any]):
        try:
            ts = dateutil_parser.parse(log.get("timestamp", datetime.now(timezone.utc).isoformat()))
        except Exception:
            ts = datetime.now(timezone.utc)
        key = self._window_key(ts, log.get("service", "unknown"))
        level = log.get("level", "INFO").upper()
        self._windows[key]["total_count"] += 1
        if level in ("ERROR", "CRITICAL", "FATAL"):
            self._windows[key]["error_count"] += 1
        elif level in ("WARN", "WARNING"):
            self._windows[key]["warn_count"] += 1
        else:
            self._windows[key]["info_count"] += 1

    def flush_old(self, current_time: datetime, es: Elasticsearch):
        current_epoch = int(current_time.timestamp())
        to_flush = [k for k in self._windows if k[0] < current_epoch - self.window_seconds * 2]
        docs = []
        for key in to_flush:
            window_start, service = key
            counts = self._windows.pop(key)
            doc = {
                "window_start": datetime.fromtimestamp(window_start, tz=timezone.utc).isoformat(),
                "service": service,
                **counts,
            }
            docs.append({"_index": "log-features", "_source": doc})
        if docs:
            helpers.bulk(es, docs)
            logger.info("Flushed %d feature windows to ES", len(docs))


class LogNormalizer:
    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        received_at = datetime.now(timezone.utc).isoformat()
        log_id = raw.get("id", str(uuid.uuid4()))
        timestamp = raw.get("timestamp", received_at)
        try:
            dateutil_parser.parse(timestamp)
        except Exception:
            timestamp = received_at

        return {
            "id": log_id,
            "source": raw.get("source", "unknown"),
            "message": raw.get("message", ""),
            "level": raw.get("level", "INFO").upper(),
            "timestamp": timestamp,
            "received_at": received_at,
            "service": raw.get("service", "unknown"),
            "host": raw.get("host", "unknown"),
            "extra_fields": raw.get("extra_fields", {}),
        }


def run():
    es = get_es_client()
    ensure_indices(es)
    normalizer = LogNormalizer()
    accumulator = WindowAccumulator(WINDOW_SECONDS)

    consumer_conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }

    for attempt in range(10):
        try:
            consumer = Consumer(consumer_conf)
            consumer.subscribe([KAFKA_TOPIC])
            logger.info("Kafka consumer subscribed to %s", KAFKA_TOPIC)
            break
        except Exception as exc:
            logger.warning("Kafka consumer attempt %d: %s", attempt + 1, exc)
            time.sleep(5)
    else:
        raise RuntimeError("Cannot create Kafka consumer")

    last_flush = datetime.now(timezone.utc)
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka error: %s", msg.error())
            else:
                try:
                    raw = json.loads(msg.value().decode("utf-8"))
                    normalized = normalizer.normalize(raw)
                    es.index(index="logs", id=normalized["id"], body=normalized)
                    accumulator.add(normalized)
                except Exception as exc:
                    logger.error("Error processing message: %s", exc)

            now = datetime.now(timezone.utc)
            if (now - last_flush).total_seconds() >= WINDOW_SECONDS:
                accumulator.flush_old(now, es)
                last_flush = now
    finally:
        consumer.close()


if __name__ == "__main__":
    run()

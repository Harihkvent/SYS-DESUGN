import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Patch confluent_kafka before importing receiver
import sys
mock_kafka = MagicMock()
mock_producer = MagicMock()
mock_kafka.Producer.return_value = mock_producer
mock_producer.produce = MagicMock()
mock_producer.poll = MagicMock()
sys.modules["confluent_kafka"] = mock_kafka

from backend.ingestion.receiver import app, LogEntry

client = TestClient(app)


class TestLogEntry:
    def test_valid_log_entry(self):
        entry = LogEntry(
            source="test-source",
            message="Hello world",
            level="INFO",
            service="my-service",
            host="host-1",
        )
        assert entry.level == "INFO"
        assert entry.timestamp is not None

    def test_level_normalized_to_upper(self):
        entry = LogEntry(
            source="s", message="m", level="info", service="svc", host="h"
        )
        assert entry.level == "INFO"

    def test_invalid_level_raises(self):
        with pytest.raises(Exception):
            LogEntry(source="s", message="m", level="TRACE", service="svc", host="h")

    def test_timestamp_defaults_to_now(self):
        entry = LogEntry(source="s", message="m", level="ERROR", service="svc", host="h")
        assert "T" in entry.timestamp

    def test_extra_fields_defaults_empty(self):
        entry = LogEntry(source="s", message="m", level="DEBUG", service="svc", host="h")
        assert entry.extra_fields == {}


class TestIngestEndpoint:
    def test_single_log_ingest(self):
        payload = {
            "source": "test",
            "message": "Test log",
            "level": "INFO",
            "service": "web",
            "host": "host-1",
        }
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] == 1
        assert len(data["ids"]) == 1

    def test_batch_log_ingest(self):
        payload = [
            {"source": "test", "message": "Log 1", "level": "INFO", "service": "web", "host": "h1"},
            {"source": "test", "message": "Log 2", "level": "ERROR", "service": "api", "host": "h2"},
        ]
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] == 2
        assert len(data["ids"]) == 2

    def test_missing_required_field(self):
        payload = {"source": "test", "level": "INFO", "service": "web", "host": "h"}
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 422

    def test_missing_service(self):
        payload = {"source": "test", "message": "msg", "level": "INFO", "host": "h"}
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 422

    def test_invalid_level(self):
        payload = {"source": "s", "message": "m", "level": "VERBOSE", "service": "svc", "host": "h"}
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 422

    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import sys

# Mock confluent_kafka and elasticsearch
sys.modules["confluent_kafka"] = MagicMock()
sys.modules["elasticsearch"] = MagicMock()
sys.modules["elasticsearch.helpers"] = MagicMock()

from backend.processing.consumer import LogNormalizer, WindowAccumulator


class TestLogNormalizer:
    def setup_method(self):
        self.normalizer = LogNormalizer()

    def test_normalize_complete_log(self):
        raw = {
            "id": "abc-123",
            "source": "app",
            "message": "test message",
            "level": "error",
            "timestamp": "2024-01-01T00:00:00Z",
            "service": "my-service",
            "host": "host-1",
            "extra_fields": {"request_id": "xyz"},
        }
        result = self.normalizer.normalize(raw)
        assert result["id"] == "abc-123"
        assert result["level"] == "ERROR"
        assert result["service"] == "my-service"
        assert "received_at" in result

    def test_normalize_missing_id_generates_uuid(self):
        raw = {"source": "s", "message": "m", "level": "INFO", "service": "svc", "host": "h"}
        result = self.normalizer.normalize(raw)
        assert len(result["id"]) == 36

    def test_normalize_invalid_timestamp_uses_received_at(self):
        raw = {"source": "s", "message": "m", "level": "INFO", "service": "svc", "host": "h", "timestamp": "not-a-date"}
        result = self.normalizer.normalize(raw)
        assert "T" in result["timestamp"]

    def test_normalize_level_uppercased(self):
        raw = {"source": "s", "message": "m", "level": "warn", "service": "svc", "host": "h"}
        result = self.normalizer.normalize(raw)
        assert result["level"] == "WARN"

    def test_normalize_defaults_unknown_fields(self):
        raw = {}
        result = self.normalizer.normalize(raw)
        assert result["source"] == "unknown"
        assert result["service"] == "unknown"
        assert result["host"] == "unknown"
        assert result["message"] == ""


class TestWindowAccumulator:
    def setup_method(self):
        self.acc = WindowAccumulator(window_seconds=60)

    def test_add_error_increments_error_count(self):
        log = {"timestamp": "2024-01-01T00:00:30Z", "service": "svc", "level": "ERROR"}
        self.acc.add(log)
        key = list(self.acc._windows.keys())[0]
        assert self.acc._windows[key]["error_count"] == 1

    def test_add_info_increments_info_count(self):
        log = {"timestamp": "2024-01-01T00:00:30Z", "service": "svc", "level": "INFO"}
        self.acc.add(log)
        key = list(self.acc._windows.keys())[0]
        assert self.acc._windows[key]["info_count"] == 1
        assert self.acc._windows[key]["error_count"] == 0

    def test_add_warn_increments_warn_count(self):
        log = {"timestamp": "2024-01-01T00:00:30Z", "service": "svc", "level": "WARN"}
        self.acc.add(log)
        key = list(self.acc._windows.keys())[0]
        assert self.acc._windows[key]["warn_count"] == 1

    def test_total_count_incremented(self):
        for level in ["INFO", "WARN", "ERROR"]:
            self.acc.add({"timestamp": "2024-01-01T00:00:30Z", "service": "svc", "level": level})
        key = list(self.acc._windows.keys())[0]
        assert self.acc._windows[key]["total_count"] == 3

    def test_different_services_separate_windows(self):
        self.acc.add({"timestamp": "2024-01-01T00:00:30Z", "service": "svc-a", "level": "ERROR"})
        self.acc.add({"timestamp": "2024-01-01T00:00:30Z", "service": "svc-b", "level": "ERROR"})
        assert len(self.acc._windows) == 2

    def test_critical_counts_as_error(self):
        log = {"timestamp": "2024-01-01T00:00:30Z", "service": "svc", "level": "CRITICAL"}
        self.acc.add(log)
        key = list(self.acc._windows.keys())[0]
        assert self.acc._windows[key]["error_count"] == 1

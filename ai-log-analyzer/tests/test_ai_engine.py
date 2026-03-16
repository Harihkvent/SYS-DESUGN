import pytest
from unittest.mock import MagicMock, patch
import sys

sys.modules["elasticsearch"] = MagicMock()
sys.modules["schedule"] = MagicMock()
sys.modules["numpy"] = MagicMock()

from backend.ai_engine.ai_engine import AnomalyDetector, RCAAgent, Clusterer, EmbeddingGenerator


class TestAnomalyDetector:
    def setup_method(self):
        self.es = MagicMock()
        self.detector = AnomalyDetector(self.es, threshold=10)

    def test_no_anomaly_below_threshold(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 5, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert len(anomalies) == 0

    def test_anomaly_above_threshold(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 15, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert len(anomalies) == 1
        assert anomalies[0]["service"] == "svc"
        assert anomalies[0]["error_count"] == 15

    def test_severity_medium_just_above_threshold(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 11, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert anomalies[0]["severity"] == "medium"

    def test_severity_high(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 21, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert anomalies[0]["severity"] == "high"

    def test_severity_critical(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 31, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert anomalies[0]["severity"] == "critical"

    def test_anomaly_has_rca(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "payment", "error_count": 20, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert "rca" in anomalies[0]
        assert "payment" in anomalies[0]["rca"]

    def test_anomaly_has_id(self):
        self.es.search.return_value = {
            "hits": {"hits": [{"_source": {"service": "svc", "error_count": 15, "window_start": "2024-01-01T00:00:00Z"}}]}
        }
        anomalies = self.detector.detect()
        assert "id" in anomalies[0]
        assert len(anomalies[0]["id"]) == 36

    def test_es_failure_returns_empty(self):
        self.es.search.side_effect = Exception("ES down")
        anomalies = self.detector.detect()
        assert anomalies == []

    def test_store_anomalies_calls_es_index(self):
        anomaly = {"id": "test-id", "service": "svc", "error_count": 15, "severity": "medium", "status": "open"}
        self.detector.store_anomalies([anomaly])
        self.es.index.assert_called_once()


class TestRCAAgent:
    def test_explain_returns_string(self):
        rca = RCAAgent()
        anomaly = {"service": "auth", "error_count": 25, "threshold": 10, "window_start": "2024-01-01T00:00:00Z"}
        result = rca.explain(anomaly)
        assert isinstance(result, str)
        assert "auth" in result
        assert "25" in result

    def test_explain_mentions_threshold(self):
        rca = RCAAgent()
        anomaly = {"service": "svc", "error_count": 15, "threshold": 10, "window_start": "t"}
        result = rca.explain(anomaly)
        assert "10" in result


class TestClusterer:
    def test_same_service_same_cluster(self):
        clusterer = Clusterer()
        anomalies = [
            {"service": "svc-a", "error_count": 11},
            {"service": "svc-a", "error_count": 13},
        ]
        clusters = clusterer.cluster(anomalies)
        assert len(clusters) == 1

    def test_different_services_different_clusters(self):
        clusterer = Clusterer()
        anomalies = [
            {"service": "svc-a", "error_count": 11},
            {"service": "svc-b", "error_count": 13},
        ]
        clusters = clusterer.cluster(anomalies)
        assert len(clusters) == 2


class TestEmbeddingGenerator:
    def test_hash_mock_returns_correct_dimensions(self):
        gen = EmbeddingGenerator()
        gen._model = None  # Force mock path
        embeddings = gen.encode(["hello world", "test text"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 64

    def test_embeddings_are_deterministic(self):
        gen = EmbeddingGenerator()
        gen._model = None
        e1 = gen.encode(["hello"])
        e2 = gen.encode(["hello"])
        assert e1 == e2

    def test_different_texts_different_embeddings(self):
        gen = EmbeddingGenerator()
        gen._model = None
        e1 = gen.encode(["hello"])
        e2 = gen.encode(["world"])
        assert e1 != e2

#!/usr/bin/env python3
"""Create Elasticsearch indices with proper mappings."""
import os
import sys
import json
try:
    from elasticsearch import Elasticsearch
except ImportError:
    print("elasticsearch package not installed. Run: pip install elasticsearch")
    sys.exit(1)

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

INDICES = {
    "logs": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "message": {"type": "text", "analyzer": "standard"},
                "level": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "received_at": {"type": "date"},
                "service": {"type": "keyword"},
                "host": {"type": "keyword"},
                "extra_fields": {"type": "object", "dynamic": True},
            }
        },
    },
    "log-features": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "window_start": {"type": "date"},
                "service": {"type": "keyword"},
                "error_count": {"type": "integer"},
                "warn_count": {"type": "integer"},
                "info_count": {"type": "integer"},
                "total_count": {"type": "integer"},
            }
        },
    },
    "anomalies": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
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
                "notified_at": {"type": "date"},
                "detected_at": {"type": "date"},
                "rca": {"type": "text"},
                "cluster": {"type": "keyword"},
            }
        },
    },
}


def main():
    print(f"Connecting to Elasticsearch at {ES_URL}...")
    es = Elasticsearch(ES_URL)

    if not es.ping():
        print("ERROR: Cannot connect to Elasticsearch")
        sys.exit(1)

    print("Connected!\n")
    for name, config in INDICES.items():
        if es.indices.exists(index=name):
            print(f"  ⚠️  Index '{name}' already exists — skipping")
        else:
            es.indices.create(index=name, body=config)
            print(f"  ✅  Created index '{name}'")

    print("\nAll indices ready:")
    for name in INDICES:
        info = es.indices.stats(index=name)
        count = info["indices"][name]["total"]["docs"]["count"]
        print(f"  {name}: {count} documents")


if __name__ == "__main__":
    main()

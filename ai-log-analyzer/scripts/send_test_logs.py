#!/usr/bin/env python3
"""Send sample log events to the ingestion service for testing."""
import random
import time
import json
from datetime import datetime, timezone
import requests

INGESTION_URL = "http://localhost:8001"
SERVICES = ["auth-service", "payment-service", "user-service", "api-gateway", "notification-service"]
HOSTS = ["pod-1", "pod-2", "pod-3", "node-a", "node-b"]
LEVELS = ["DEBUG", "INFO", "INFO", "INFO", "WARN", "ERROR", "CRITICAL"]

ERROR_MESSAGES = [
    "Database connection timeout after 30s",
    "Failed to authenticate user: invalid credentials",
    "Payment processing failed: insufficient funds",
    "Redis cache miss: key expired",
    "HTTP 500 Internal Server Error on /api/checkout",
    "Memory usage critical: 95% heap used",
    "Circuit breaker OPEN for downstream-service",
    "Rate limit exceeded for client 192.168.1.100",
]

INFO_MESSAGES = [
    "Request processed successfully in 45ms",
    "User login successful: user_id=1234",
    "Cache warmed up with 500 entries",
    "Health check passed",
    "Background job completed: sent 150 emails",
    "Config reloaded from etcd",
    "Graceful shutdown initiated",
]

def random_log(service: str = None, force_error: bool = False) -> dict:
    svc = service or random.choice(SERVICES)
    level = "ERROR" if force_error else random.choice(LEVELS)
    msg = random.choice(ERROR_MESSAGES if level in ("ERROR", "CRITICAL") else INFO_MESSAGES)
    return {
        "source": "simulator",
        "message": msg,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": svc,
        "host": random.choice(HOSTS),
        "extra_fields": {
            "request_id": f"req-{random.randint(10000, 99999)}",
            "duration_ms": random.randint(1, 2000),
        },
    }


def send_log(log: dict) -> bool:
    try:
        resp = requests.post(f"{INGESTION_URL}/ingest", json=log, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def send_batch(logs: list) -> bool:
    try:
        resp = requests.post(f"{INGESTION_URL}/ingest", json=logs, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print(f"  Batch accepted: {data['accepted']} logs")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def simulate_normal_traffic(count: int = 50):
    print(f"\n📤 Sending {count} normal traffic logs...")
    for i in range(count):
        log = random_log()
        ok = send_log(log)
        if ok:
            print(f"  [{i+1}/{count}] {log['level']:8} | {log['service']:25} | {log['message'][:50]}")
        time.sleep(0.05)


def simulate_anomaly(service: str = "payment-service", burst: int = 20):
    print(f"\n🚨 Simulating anomaly burst ({burst} errors) on {service}...")
    logs = [random_log(service=service, force_error=True) for _ in range(burst)]
    send_batch(logs)


def simulate_mixed_batch():
    print("\n📦 Sending mixed batch of 30 logs...")
    logs = [random_log() for _ in range(30)]
    send_batch(logs)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send test logs to ingestion service")
    parser.add_argument("--url", default=INGESTION_URL, help="Ingestion service URL")
    parser.add_argument("--mode", choices=["normal", "anomaly", "batch", "continuous"], default="normal")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--service", default="payment-service")
    args = parser.parse_args()

    INGESTION_URL = args.url

    print(f"🔗 Target: {INGESTION_URL}")

    if args.mode == "normal":
        simulate_normal_traffic(args.count)
    elif args.mode == "anomaly":
        simulate_normal_traffic(20)
        simulate_anomaly(service=args.service, burst=args.count)
    elif args.mode == "batch":
        simulate_mixed_batch()
    elif args.mode == "continuous":
        print("🔄 Running continuous simulation (Ctrl+C to stop)...")
        iteration = 0
        while True:
            iteration += 1
            simulate_normal_traffic(10)
            if iteration % 5 == 0:
                simulate_anomaly(service=random.choice(SERVICES), burst=15)
            time.sleep(5)

    print("\n✅ Done!")

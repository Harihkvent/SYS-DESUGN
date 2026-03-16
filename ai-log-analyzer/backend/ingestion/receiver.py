import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from confluent_kafka import Producer, KafkaException
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ingestion")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "raw-logs")

app = FastAPI(title="Log Ingestion Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_producer: Optional[Producer] = None


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        conf = {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "ingestion-service",
            "acks": "all",
            "retries": 5,
            "retry.backoff.ms": 500,
        }
        _producer = Producer(conf)
        logger.info("Kafka producer created for %s", KAFKA_BOOTSTRAP_SERVERS)
    return _producer


def delivery_callback(err, msg):
    if err:
        logger.error("Kafka delivery error: %s", err)
    else:
        logger.debug("Delivered to %s [%d] offset %d", msg.topic(), msg.partition(), msg.offset())


VALID_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}


class LogEntry(BaseModel):
    source: str = Field(..., min_length=1, description="Log source system")
    message: str = Field(..., min_length=1, description="Log message text")
    level: str = Field(..., description="Log level: DEBUG/INFO/WARN/ERROR/CRITICAL")
    timestamp: Optional[str] = Field(None, description="ISO-8601 timestamp; defaults to now")
    service: str = Field(..., min_length=1, description="Originating service name")
    host: str = Field(..., min_length=1, description="Host or pod name")
    extra_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator("level")
    def validate_level(cls, v: str) -> str:
        upper = v.upper()
        if upper not in VALID_LEVELS:
            raise ValueError(f"level must be one of {VALID_LEVELS}, got '{v}'")
        return upper

    @validator("timestamp", pre=True, always=True)
    def default_timestamp(cls, v: Optional[str]) -> str:
        if v is None:
            return datetime.now(timezone.utc).isoformat()
        return v


class IngestResponse(BaseModel):
    accepted: int
    ids: List[str]


def _publish_entry(producer: Producer, entry: LogEntry) -> str:
    log_id = str(uuid.uuid4())
    payload = entry.dict()
    payload["id"] = log_id
    producer.produce(
        KAFKA_TOPIC,
        key=entry.service.encode(),
        value=json.dumps(payload).encode(),
        callback=delivery_callback,
    )
    return log_id


@app.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(body: Union[LogEntry, List[LogEntry]]):
    entries: List[LogEntry] = [body] if isinstance(body, LogEntry) else body
    if not entries:
        raise HTTPException(status_code=422, detail="Empty batch")

    try:
        producer = get_producer()
    except KafkaException as exc:
        logger.error("Cannot connect to Kafka: %s", exc)
        raise HTTPException(status_code=503, detail="Kafka unavailable")

    ids: List[str] = []
    for entry in entries:
        log_id = _publish_entry(producer, entry)
        ids.append(log_id)

    producer.poll(0)
    return IngestResponse(accepted=len(ids), ids=ids)


@app.get("/health")
async def health():
    try:
        get_producer()
        kafka_ok = True
    except Exception:
        kafka_ok = False
    return {
        "status": "ok" if kafka_ok else "degraded",
        "kafka": "connected" if kafka_ok else "unavailable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    uvicorn.run("receiver:app", host="0.0.0.0", port=8001, reload=False)

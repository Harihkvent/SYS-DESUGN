import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch, NotFoundError
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("api")

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

app = FastAPI(title="AI Log Analyzer API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_es: Optional[Elasticsearch] = None


def get_es() -> Elasticsearch:
    global _es
    if _es is None or not _es.ping():
        _es = Elasticsearch(ES_URL)
    return _es


class NLQueryRequest(BaseModel):
    query: str
    page: int = 1
    page_size: int = 20


@app.get("/health")
async def health():
    try:
        es = get_es()
        es_ok = es.ping()
    except Exception:
        es_ok = False
    return {
        "status": "ok" if es_ok else "degraded",
        "elasticsearch": "connected" if es_ok else "unavailable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/v1/logs")
async def get_logs(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    es = get_es()
    must = []
    if service:
        must.append({"term": {"service": service}})
    if level:
        must.append({"term": {"level": level.upper()}})
    if q:
        must.append({"match": {"message": q}})
    if from_ or to:
        range_filter: Dict[str, Any] = {}
        if from_:
            range_filter["gte"] = from_
        if to:
            range_filter["lte"] = to
        must.append({"range": {"timestamp": range_filter}})

    body = {
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
        "sort": [{"timestamp": "desc"}],
        "from": (page - 1) * page_size,
        "size": page_size,
    }
    try:
        resp = es.search(index="logs", body=body)
        hits = resp["hits"]
        return {
            "total": hits["total"]["value"],
            "page": page,
            "page_size": page_size,
            "logs": [h["_source"] for h in hits["hits"]],
        }
    except Exception as exc:
        logger.error("ES query error: %s", exc)
        return {"total": 0, "page": page, "page_size": page_size, "logs": []}


@app.get("/v1/anomalies")
async def get_anomalies(
    service: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    es = get_es()
    must = []
    if service:
        must.append({"term": {"service": service}})
    if status:
        must.append({"term": {"status": status}})

    body = {
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
        "sort": [{"detected_at": "desc"}],
        "from": (page - 1) * page_size,
        "size": page_size,
    }
    try:
        resp = es.search(index="anomalies", body=body)
        hits = resp["hits"]
        return {
            "total": hits["total"]["value"],
            "page": page,
            "page_size": page_size,
            "anomalies": [h["_source"] for h in hits["hits"]],
        }
    except Exception as exc:
        logger.error("ES query error: %s", exc)
        return {"total": 0, "page": page, "page_size": page_size, "anomalies": []}


@app.get("/v1/incidents/{incident_id}")
async def get_incident(incident_id: str):
    es = get_es()
    try:
        doc = es.get(index="anomalies", id=incident_id)
        return doc["_source"]
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except Exception as exc:
        logger.error("ES get error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error")


@app.post("/v1/query")
async def nl_query(request: NLQueryRequest):
    es = get_es()
    keywords = request.query.strip()
    if not keywords:
        raise HTTPException(status_code=422, detail="query must not be empty")

    body = {
        "query": {
            "multi_match": {
                "query": keywords,
                "fields": ["message", "service", "host", "level"],
                "type": "best_fields",
            }
        },
        "sort": [{"timestamp": "desc"}],
        "from": (request.page - 1) * request.page_size,
        "size": request.page_size,
    }
    try:
        resp = es.search(index="logs", body=body)
        hits = resp["hits"]
        logs = [h["_source"] for h in hits["hits"]]
        total = hits["total"]["value"]
        analysis = (
            f"Found {total} log entries matching '{keywords}'. "
            + (f"Top result from service '{logs[0].get('service')}': {logs[0].get('message')[:200]}" if logs else "No matching logs found.")
        )
        return {
            "total": total,
            "logs": logs,
            "analysis": analysis,
        }
    except Exception as exc:
        logger.error("NL query error: %s", exc)
        return {"total": 0, "logs": [], "analysis": f"Search failed: {exc}"}


@app.get("/v1/stats")
async def get_stats():
    es = get_es()
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    try:
        resp = es.search(
            index="logs",
            body={
                "query": {"range": {"timestamp": {"gte": since}}},
                "aggs": {
                    "by_level": {"terms": {"field": "level", "size": 10}},
                    "over_time": {
                        "date_histogram": {
                            "field": "timestamp",
                            "fixed_interval": "5m",
                            "min_doc_count": 0,
                        }
                    },
                },
                "size": 0,
            },
        )
        level_counts = {
            b["key"]: b["doc_count"] for b in resp["aggregations"]["by_level"]["buckets"]
        }
        time_series = [
            {"time": b["key_as_string"], "count": b["doc_count"]}
            for b in resp["aggregations"]["over_time"]["buckets"]
        ]
        total = resp["hits"]["total"]["value"]

        anomaly_resp = es.count(index="anomalies", body={"query": {"term": {"status": "open"}}})
        open_anomalies = anomaly_resp["count"]

        error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
        error_rate = round((error_count / total * 100), 2) if total > 0 else 0.0

        return {
            "total_logs_last_hour": total,
            "open_anomalies": open_anomalies,
            "error_rate_percent": error_rate,
            "level_counts": level_counts,
            "time_series": time_series,
        }
    except Exception as exc:
        logger.error("Stats error: %s", exc)
        return {
            "total_logs_last_hour": 0,
            "open_anomalies": 0,
            "error_rate_percent": 0.0,
            "level_counts": {},
            "time_series": [],
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

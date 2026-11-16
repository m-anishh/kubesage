import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator, metrics

from app import faults

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("orders-api")

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments-api:8000")
# Buckets above 1 s are required: the HighP95Latency alert compares P95 against 1 s,
# and histogram_quantile can never report a value above the largest finite bucket.
LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


@asynccontextmanager
async def lifespan(_: FastAPI):
    faults.check_crash()
    faults.start_memory_leak()
    faults.log_injection()
    log.info("orders-api started, payments at %s", PAYMENTS_URL)
    yield


app = FastAPI(title="orders-api", lifespan=lifespan)
Instrumentator(excluded_handlers=["/metrics", "/healthz"]).add(
    metrics.default(latency_lowr_buckets=LATENCY_BUCKETS)
).instrument(app).expose(app, include_in_schema=False)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/orders")
async def orders() -> dict:
    await faults.maybe_slow()
    if faults.should_fail():
        log.error("order lookup failed: database connection reset")
        raise HTTPException(status_code=500, detail="internal error")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{PAYMENTS_URL}/pay", json={"order_id": 42, "amount": 19.99})
            resp.raise_for_status()
            payment = resp.json()
    except httpx.HTTPError as exc:
        log.error("payments-api call failed: %s", exc)
        raise HTTPException(status_code=502, detail="payment service unavailable") from exc
    return {"orders": [{"id": 42, "amount": 19.99, "payment": payment}]}

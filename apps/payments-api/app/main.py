import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from pydantic import BaseModel

from app import faults

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("payments-api")

# Buckets above 1 s are required for the HighP95Latency alert (threshold 1 s).
LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


class Payment(BaseModel):
    order_id: int
    amount: float


@asynccontextmanager
async def lifespan(_: FastAPI):
    faults.check_crash()
    faults.start_memory_leak()
    faults.log_injection()
    log.info("payments-api started")
    yield


app = FastAPI(title="payments-api", lifespan=lifespan)
Instrumentator(excluded_handlers=["/metrics", "/healthz"]).add(
    metrics.default(latency_lowr_buckets=LATENCY_BUCKETS)
).instrument(app).expose(app, include_in_schema=False)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/pay")
async def pay(payment: Payment) -> dict:
    await faults.maybe_slow()
    if faults.should_fail():
        log.error("payment %s failed: card processor returned 503", payment.order_id)
        raise HTTPException(status_code=500, detail="payment failed")
    return {"status": "paid", "payment_id": str(uuid.uuid4()), "order_id": payment.order_id}

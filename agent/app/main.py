import asyncio
import hashlib
import json
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from fastapi.concurrency import run_in_threadpool
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

from app import agent, config, github_issues, rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("kubesage")

DEDUPE_SECONDS = 4 * 3600  # same as Alertmanager repeat_interval

_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_INVESTIGATIONS)
_in_flight: set[str] = set()
_recent: dict[str, float] = {}


def _ensure_labels() -> None:
    try:
        github_issues.ensure_labels()
    except Exception as exc:  # noqa: BLE001 - issues still work if labels already exist
        log.warning("could not create GitHub labels: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("model=%s namespaces=%s dry_run=%s", config.MODEL_ID, config.ALLOWED_NAMESPACES, config.DRY_RUN)
    rag.ingest_in_background()
    if not config.DRY_RUN:
        threading.Thread(target=_ensure_labels, daemon=True).start()
    yield


app = FastAPI(title="kubesage-agent", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


def fingerprint(alert: dict) -> str:
    fp = alert.get("fingerprint")
    if fp:
        return str(fp)
    labels = json.dumps(alert.get("labels", {}), sort_keys=True)
    return hashlib.sha256(labels.encode()).hexdigest()[:16]


def _recently_done(fp: str) -> bool:
    now = time.time()
    for key in [k for k, t in _recent.items() if now - t > DEDUPE_SECONDS]:
        del _recent[key]
    return fp in _recent


async def handle_firing(fp: str, alert: dict, open_issue: bool = True) -> dict:
    _in_flight.add(fp)
    try:
        if open_issue and not config.DRY_RUN:
            existing = await run_in_threadpool(github_issues.find_open_issue, fp)
            if existing:
                log.info("alert %s already has open issue #%s, skipping", fp, existing)
                return {"fingerprint": fp, "skipped": f"open issue #{existing}"}
        async with _semaphore:
            result = await run_in_threadpool(agent.investigate, alert)
        log.info("investigation %s: %s", fp, json.dumps(result)[:1000])
        if open_issue and not config.DRY_RUN:
            result["issue_url"] = await run_in_threadpool(github_issues.create_issue, alert, result, fp)
        _recent[fp] = time.time()
        return {"fingerprint": fp, **result}
    except Exception as exc:  # noqa: BLE001 - log and keep serving other alerts
        log.exception("handling alert %s failed", fp)
        return {"fingerprint": fp, "error": str(exc)[:300]}
    finally:
        _in_flight.discard(fp)


async def handle_resolved(fp: str) -> None:
    _recent.pop(fp, None)
    if config.DRY_RUN:
        return
    try:
        number = await run_in_threadpool(github_issues.resolve_issue, fp)
        log.info("alert %s resolved, issue %s", fp, f"#{number} closed" if number else "not found")
    except Exception:  # noqa: BLE001
        log.exception("closing issue for %s failed", fp)


@app.post("/webhook/alertmanager")
async def alertmanager_webhook(payload: dict, background: BackgroundTasks, sync: bool = False) -> dict:
    """Alertmanager sends one payload with one or more alerts.

    sync=true runs the investigation inline and returns the result (for curl tests and the scorecard);
    it skips de-duplication and does not open an issue.
    """
    accepted, skipped, results = [], [], []
    for alert in payload.get("alerts", []):
        fp = fingerprint(alert)
        if alert.get("status") == "resolved":
            background.add_task(handle_resolved, fp)
            skipped.append({"fingerprint": fp, "reason": "resolved"})
        elif sync:
            results.append(await handle_firing(fp, alert, open_issue=False))
        elif fp in _in_flight or _recently_done(fp):
            skipped.append({"fingerprint": fp, "reason": "duplicate"})
        else:
            _in_flight.add(fp)
            background.add_task(handle_firing, fp, alert)
            accepted.append(fp)
    return {"accepted": accepted, "skipped": skipped, "results": results}


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    async with _semaphore:
        return await run_in_threadpool(agent.chat, req.question)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "runbooks_indexed": rag.is_ready(), "in_flight": len(_in_flight)}

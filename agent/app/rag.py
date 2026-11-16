"""RAG over runbooks: split by '## ' heading, embed with Titan V2, store and search in Qdrant.

Qdrant has no disk in this project, so ingest() runs at every agent start.
"""

import json
import logging
import threading
import time
import uuid
from functools import lru_cache

import boto3
from botocore.config import Config
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app import config

log = logging.getLogger("rag")
_ready = threading.Event()


@lru_cache
def _bedrock():
    return boto3.client(
        "bedrock-runtime", region_name=config.AWS_REGION, config=Config(retries={"max_attempts": 3, "mode": "adaptive"})
    )


@lru_cache
def _qdrant() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL, timeout=10)


def embed(text: str) -> list[float]:
    body = json.dumps({"inputText": text[:8000], "dimensions": config.EMBED_DIMENSIONS, "normalize": True})
    resp = _bedrock().invoke_model(modelId=config.EMBED_MODEL_ID, body=body)
    return json.loads(resp["body"].read())["embedding"]


def split_runbook(source: str, text: str) -> list[dict]:
    """One chunk per '## ' section; the '# ' title is prefixed to each chunk for context."""
    title, chunks, heading, lines = "", [], None, []
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            if heading and any(x.strip() for x in lines):
                chunks.append({"source": source, "heading": heading, "text": "\n".join(lines).strip()})
            heading, lines = line[3:].strip(), []
        elif heading:
            lines.append(line)
    if heading and any(x.strip() for x in lines):
        chunks.append({"source": source, "heading": heading, "text": "\n".join(lines).strip()})
    for c in chunks:
        c["title"] = title
    return chunks


def load_chunks() -> list[dict]:
    chunks = []
    for path in sorted(config.RUNBOOK_DIR.glob("*.md")):
        chunks.extend(split_runbook(path.name, path.read_text(encoding="utf-8")))
    return chunks


def ingest() -> int:
    chunks = load_chunks()
    q = _qdrant()
    if q.collection_exists(config.RUNBOOK_COLLECTION):
        q.delete_collection(config.RUNBOOK_COLLECTION)
    q.create_collection(
        config.RUNBOOK_COLLECTION,
        vectors_config=VectorParams(size=config.EMBED_DIMENSIONS, distance=Distance.COSINE),
    )
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c['source']}#{c['heading']}")),
            vector=embed(f"{c['title']}: {c['heading']}\n{c['text']}"),
            payload=c,
        )
        for c in chunks
    ]
    q.upsert(config.RUNBOOK_COLLECTION, points=points)
    _ready.set()
    log.info("indexed %d runbook chunks from %s", len(points), config.RUNBOOK_DIR)
    return len(points)


def ingest_in_background(retry_seconds: int = 30) -> None:
    """Qdrant or Bedrock may not be ready when the pod starts: keep retrying without blocking startup."""

    def loop() -> None:
        while not _ready.is_set():
            try:
                ingest()
            except Exception as exc:  # noqa: BLE001 - any failure just means "try again later"
                log.warning("runbook ingest failed, retrying in %ss: %s", retry_seconds, exc)
                time.sleep(retry_seconds)

    threading.Thread(target=loop, daemon=True, name="rag-ingest").start()


def is_ready() -> bool:
    return _ready.is_set()


def search(query: str, limit: int = 3) -> list[dict] | str:
    if not _ready.is_set():
        return "runbooks are not indexed yet; continue without them"
    hits = _qdrant().query_points(config.RUNBOOK_COLLECTION, query=embed(query), limit=limit).points
    return [
        {
            "runbook": f"{h.payload['source']} — {h.payload['heading']}",
            "score": round(h.score, 3),
            "text": h.payload["text"][:1200],
        }
        for h in hits
    ]

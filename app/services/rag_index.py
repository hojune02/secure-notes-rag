from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib

import httpx
import joblib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.chunk import Chunk
from app.models.document import Document
from app.core.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")

EMBED_BATCH_SIZE = 64


def user_index_path(user_id: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"embed_index_{user_id}.joblib"


@dataclass
class Citation:
    chunk_id: str
    document_id: str
    score: float
    snippet: str


def _snippet(text: str, max_len: int = 260) -> str:
    t = " ".join(text.split())
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts via Ollama /api/embed, batched."""
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.ollama_embed_model, "input": batch},
            timeout=settings.ollama_timeout,
        )
        resp.raise_for_status()
        all_embeddings.extend(resp.json()["embeddings"])

    return np.array(all_embeddings, dtype=np.float32)


def rebuild_index_user(db: Session, user_id: str) -> None:
    """Rebuild Ollama embedding index for a user's chunks and persist to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    chunks = db.scalars(
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.owner_id == user_id)
        .order_by(Chunk.created_at.asc())
    ).all()
    texts = [c.text for c in chunks]
    chunk_ids = [str(c.id) for c in chunks]
    doc_ids = [str(c.document_id) for c in chunks]

    if not texts:
        joblib.dump(
            {"matrix": None, "chunk_ids": [], "doc_ids": [], "id_to_row": {}},
            user_index_path(user_id),
        )
        return

    matrix = _embed_texts(texts)
    id_to_row = {cid: i for i, cid in enumerate(chunk_ids)}

    joblib.dump(
        {
            "matrix": matrix,
            "chunk_ids": chunk_ids,
            "doc_ids": doc_ids,
            "id_to_row": id_to_row,
        },
        user_index_path(user_id),
    )


def _load_index(db: Session, user_id: str) -> dict[str, Any]:
    if not user_index_path(user_id).exists():
        rebuild_index_user(db, user_id)
    return joblib.load(user_index_path(user_id))


def query_index_user(
    db: Session,
    user_id: str,
    question: str,
    top_k: int = 5,
    candidate_chunk_ids: list[str] | None = None,
    dedupe: bool = True,
) -> list[Citation]:
    """Semantic cosine similarity search using Ollama embeddings."""
    payload = _load_index(db, user_id)

    matrix = payload["matrix"]
    chunk_ids: list[str] = payload["chunk_ids"]
    doc_ids: list[str] = payload["doc_ids"]
    id_to_row: dict[str, int] = payload.get("id_to_row", {})

    if matrix is None or not chunk_ids:
        return []

    q_vec = _embed_texts([question])

    k = max(1, min(int(top_k), 20))

    # Candidate slicing: choose subset of row indices
    if candidate_chunk_ids:
        rows = [id_to_row.get(cid) for cid in candidate_chunk_ids]
        rows = [r for r in rows if r is not None]
    else:
        rows = None

    if rows:
        sub_matrix = matrix[rows]
        sims = cosine_similarity(q_vec, sub_matrix).flatten()
        ranked = sorted(zip(rows, sims), key=lambda x: x[1], reverse=True)[: max(k * 3, 20)]
        global_rows = [r for r, _ in ranked]
        global_scores = [float(s) for _, s in ranked]
    else:
        sims = cosine_similarity(q_vec, matrix).flatten()
        global_rows = np.argsort(-sims)[: max(k * 3, 20)].tolist()
        global_scores = [float(sims[i]) for i in global_rows]

    citations: list[Citation] = []
    seen = set()

    for row, score in zip(global_rows, global_scores):
        cid = chunk_ids[row]
        did = doc_ids[row]

        chunk = db.get(Chunk, cid)
        if not chunk:
            continue

        snip = _snippet(chunk.text)

        if dedupe:
            h = hashlib.sha256(snip.lower().encode("utf-8")).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)

        citations.append(Citation(chunk_id=cid, document_id=did, score=score, snippet=snip))
        if len(citations) >= k:
            break

    return citations

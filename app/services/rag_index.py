from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.chunk import Chunk
from app.models.document import Document

DATA_DIR = Path("data")

# Day 4, user-insensitive chunks
INDEX_PATH = DATA_DIR / "tfidf_index.joblib"

# Day 5 per-user indexing
def user_index_path(user_id: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"tfidf_index_{user_id}.joblib"

@dataclass
class Citation:
    chunk_id: str
    document_id: str
    score: float
    snippet: str


def _snippet(text: str, max_len: int = 260) -> str:
    t = " ".join(text.split())
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


def rebuild_index_user(db: Session, user_id: str) -> None:
    """
    Rebuild TF-IDF artifacts for all chunks and persist to disk.
    Day 4: also store a chunk_id -> row index map for fast slicing.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # chunks = db.scalars(select(Chunk).order_by(Chunk.created_at.asc())).all()
    # Day 5, now we only extract chunks from the specific user's uploaded docs.
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
            {"vectorizer": None, "matrix": None, "chunk_ids": [], "doc_ids": [], "id_to_row": {}},
            user_index_path(user_id),
        )
        return

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=50_000,
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(texts)

    id_to_row = {cid: i for i, cid in enumerate(chunk_ids)}

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "matrix": matrix,
            "chunk_ids": chunk_ids,
            "doc_ids": doc_ids,
            "id_to_row": id_to_row,
        },
        user_index_path(user_id),
    )


def _load_index(db: Session, user_id: str) -> dict[str, Any]:
    # if not INDEX_PATH.exists():
    #     rebuild_index(db)
    # return joblib.load(INDEX_PATH)

    # Day 5, now loading index is performed per-user.
    if not user_index_path(user_id):
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
    """
    TF-IDF cosine similarity search.
    Day 4: If candidate_chunk_ids provided, restrict similarity to those rows (hybrid-ish retrieval).
    Day 4: Deduplicate near-identical citations (by snippet hash) to avoid repeats.
    """
    payload = _load_index(db, user_id)

    vectorizer = payload["vectorizer"]
    matrix = payload["matrix"]
    chunk_ids: list[str] = payload["chunk_ids"]
    doc_ids: list[str] = payload["doc_ids"]
    id_to_row: dict[str, int] = payload.get("id_to_row", {})

    if vectorizer is None or matrix is None or not chunk_ids:
        return []

    q_vec = vectorizer.transform([question])

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
        # Map back to global row index
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
            # Deduplicate by hash of normalized snippet prefix
            h = hashlib.sha256(snip.lower().encode("utf-8")).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)

        citations.append(Citation(chunk_id=cid, document_id=did, score=score, snippet=snip))
        if len(citations) >= k:
            break

    return citations

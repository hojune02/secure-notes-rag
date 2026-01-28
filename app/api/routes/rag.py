from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from app.schemas.rag import RagQueryRequest, RagQueryResponse, RagUploadResponse, RagCitation
from app.services.rag_index import rebuild_index_user, query_index_user

from sqlalchemy import select, or_
from app.services.rag_query_utils import extract_keywords

from fastapi import BackgroundTasks
from sqlalchemy import func
from app.api.rate_limit import rate_limit_user

from app.services.audit import audit

router = APIRouter(prefix="/rag", tags=["rag"])

import re

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

def chunk_text(text: str, target_chars: int = 1800, overlap_sentences: int = 2) -> list[str]:
    """
    Paragraph + sentence-aware chunker.
    - Split by paragraphs
    - Split long paragraphs into sentences
    - Accumulate into chunks around target_chars
    - Overlap a few sentences between chunks
    """
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []

    def flush(b: list[str]):
        s = " ".join(b).strip()
        if s:
            chunks.append(s)

    for p in paragraphs:
        if len(p) <= target_chars:
            units = [p]
        else:
            units = [s.strip() for s in _SENT_SPLIT.split(p) if s.strip()]

        for u in units:
            if not buf:
                buf = [u]
                continue

            if len(" ".join(buf)) + 1 + len(u) > target_chars:
                flush(buf)
                tail = buf[-overlap_sentences:] if overlap_sentences > 0 else []
                buf = tail + [u]
            else:
                buf.append(u)

    flush(buf)

    # Merge tiny trailing fragments into previous chunk
    merged: list[str] = []
    for ch in chunks:
        if merged and len(ch) < 320:
            merged[-1] = (merged[-1] + " " + ch).strip()
        else:
            merged.append(ch)

    return merged

def ingest_document_job(document_id: str, user_id: str, text: str) -> None:
    """
    Runs in BackgroundTasks: chunk -> insert chunks -> build per-user index -> mark ready/failed.
    NOTE: Because BackgroundTasks runs after response, we must create our own DB session.
    """
    from app.db.session import SessionLocal
    from app.services.rag_index import rebuild_index_user

    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if not doc or str(doc.owner_id) != str(user_id):
            return

        # mark processing
        doc.status = "processing"
        doc.ingest_error = None
        db.add(doc)
        db.commit()

        chunks = chunk_text(text)
        if not chunks:
            doc.status = "failed"
            doc.ingest_error = "No text content found after decoding/chunking."
            db.add(doc)
            db.commit()
            return

        # Insert chunks
        for idx, ch in enumerate(chunks):
            db.add(
                Chunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    text=ch,
                    metadata={"filename": doc.filename, "chunk_index": idx, "char_len": len(ch)},
                )
            )
        db.commit()

        # Build per-user index
        rebuild_index_user(db, user_id=str(user_id))

        # Mark ready
        doc.status = "ready"
        doc.num_chunks = len(chunks)
        doc.processed_at = func.now()
        db.add(doc)
        db.commit()

    except Exception as e:
        # Best effort: record failure
        try:
            doc = db.get(Document, document_id)
            if doc:
                doc.status = "failed"
                doc.ingest_error = str(e)[:2000]
                db.add(doc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/documents/upload", response_model=RagUploadResponse, status_code=status.HTTP_201_CREATED,
dependencies=[Depends(rate_limit_user("rag_upload", 3, 60))])
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ("text/plain", "text/markdown", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Text uploads only for now")

    raw = file.file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")

    # Create doc row first, mark as processing
    doc = Document(
        owner_id=current_user.id,
        filename=file.filename or "uploaded.txt",
        content_type=file.content_type or "text/plain",
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run ingestion after response returns
    background_tasks.add_task(ingest_document_job, str(doc.id), str(current_user.id), text)

    audit(db, current_user.id, "rag.upload", {"role": current_user.role, "uploaded_file": file.filename, "file_id": doc.id})
    # Service-grade: num_chunks unknown until finished
    return RagUploadResponse(document_id=doc.id, num_chunks=0, filename=doc.filename)



@router.post("/query", response_model=RagQueryResponse,
dependencies=[Depends(rate_limit_user("rag_query", 60, 60))])
def rag_query(
    payload: RagQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    
    keywords = extract_keywords(payload.question, max_terms=6)

    candidate_ids: list[str] | None = None
    if keywords:
        # Find candidate chunks in DB using simple keyword presence
        # OR together a few ILIKE filters: text ILIKE '%term%'
        conditions = [Chunk.text.ilike(f"%{kw}%") for kw in keywords]
        candidates = db.scalars(
            select(Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.owner_id == current_user.id)
            .where(or_(*conditions))
            .limit(2000)
        ).all()
        candidate_ids = [str(cid) for cid in candidates] if candidates else None


    # Day 3: we won’t scope retrieval per-user yet (single-user assumption),
    # but we already store owner_id so Day 5 isolation is easy.
    citations = query_index_user(db, str(current_user.id), payload.question, top_k=payload.top_k, candidate_chunk_ids=candidate_ids, dedupe=True)

    # Basic answer for Day 3: return top citation snippet (extractive baseline).
    if not citations:
        return RagQueryResponse(answer="I couldn't find relevant passages in your uploaded documents.", citations=[])
    
    # Day 4: Confidence gating
    ABS_THRESHOLD = 0.18
    GAP_THRESHOLD = 0.02

    top = citations[0].score
    second = citations[1].score if len(citations) > 1 else 0.0

    abstain = (top < ABS_THRESHOLD) or ((top - second) < GAP_THRESHOLD)

    if abstain:
        answer = (
            "I couldn't find strong support for that in your uploaded documents. "
            "Try a more specific question or upload a document that explicitly contains the answer."
        )
    else:
        # Day 4 baseline: extractive answer from best chunk
        answer = citations[0].snippet

    # Convert to response schema types
    out_citations = [
        RagCitation(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            score=c.score,
            snippet=c.snippet,
        )
        for c in citations
    ]

    audit(db, current_user.id, "rag.query", {"role": current_user.role, "question_len": len(payload.question), "top_k": payload.top_k})

    return RagQueryResponse(answer=answer, citations=out_citations)


# Day 5: list, get, and delete documents belonging to a user

@router.get("/documents", response_model=dict)
def list_documents(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = db.scalars(
        select(Document)
        .where(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "items": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "status": d.status,
                "num_chunks": d.num_chunks,
                "created_at": d.created_at,
                "processed_at": d.processed_at,
                "ingest_error": d.ingest_error,
            }
            for d in docs
        ],
        "limit": limit,
        "offset": offset,
        "total": len(docs),
    }

@router.get("/documents/{document_id}", response_model=dict)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.get(Document, document_id)
    if not doc or str(doc.owner_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="document not found")

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "num_chunks": doc.num_chunks,
        "created_at": doc.created_at,
        "processed_at": doc.processed_at,
        "ingest_error": doc.ingest_error,
    }

from app.services.rag_index import rebuild_index_user

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.get(Document, document_id)
    if not doc or str(doc.owner_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="document not found")

    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="document is still processing")

    db.delete(doc)
    db.commit()

    rebuild_index_user(db, user_id=str(current_user.id))

    audit(db, current_user.id, "rag.delete", {"role": current_user.role, "deleted_file": doc.filename, "deleted_file_id": doc.id})
    return

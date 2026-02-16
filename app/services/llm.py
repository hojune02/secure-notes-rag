from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context passages. If the context does not contain enough information "
    "to answer, say so honestly. Do not make up facts. Cite which passage you drew "
    "from when possible."
)


def _build_prompt(question: str, context_chunks: list[str]) -> str:
    numbered = "\n\n".join(
        f"[Passage {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    return f"Context:\n{numbered}\n\nQuestion: {question}\n\nAnswer:"


def generate_answer(question: str, context_chunks: list[str]) -> str | None:
    """
    Call Ollama's /api/generate endpoint with retrieved context.
    Returns the generated answer text, or None on any failure.
    """
    prompt = _build_prompt(question, context_chunks)

    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": _SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
            },
            timeout=settings.ollama_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("response", "").strip()
        return answer if answer else None
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("Ollama unavailable, falling back to extractive: %s", exc)
        return None
    except Exception as exc:
        logger.error("Ollama generate failed: %s", exc)
        return None

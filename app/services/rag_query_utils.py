import re

# Small English stopword set (keep it minimal; easy to tune)
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "by", "at", "from",
    "is", "are", "was", "were", "be", "been", "being", "it", "this", "that", "these", "those",
    "what", "who", "whom", "which", "when", "where", "why", "how", "do", "does", "did",
    "i", "you", "we", "they", "he", "she", "them", "him", "her", "my", "your", "our", "their",
}

_WORD = re.compile(r"[A-Za-z]{2,}")

def extract_keywords(question: str, max_terms: int = 6) -> list[str]:
    """
    Extract up to max_terms keywords from question.
    Lowercase, remove stopwords, keep original order, dedupe.
    """
    terms = [t.lower() for t in _WORD.findall(question)]
    terms = [t for t in terms if t not in STOPWORDS]

    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= max_terms:
            break
    return out

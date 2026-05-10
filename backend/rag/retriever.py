from rag.embedder import get_client, get_embedder
import os

_reranker = None


def _rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "0") == "1"


def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except ImportError:
            return None
    return _reranker


def retrieve_for_jd(jd_text: str, jd_id: str, top_k: int = 20) -> dict[str, float]:
    """
    Returns {candidate_id: semantic_sim_score} for all candidates in this JD's collection.
    Uses bi-encoder retrieval → cross-encoder reranking.
    """
    if not _rag_enabled():
        return {}
    
    client = get_client()
    if not client:
        return {}

    try:
        col = client.get_collection(f"jd_{jd_id}")
    except Exception:
        return {}   # collection doesn't exist yet

    embedder  = get_embedder()
    if not embedder:
        return {}
    query_emb = embedder.encode(jd_text).tolist()

    # Bi-encoder retrieval — get top_k chunks
    count = col.count()
    if count == 0:
        return {}

    results = col.query(
        query_embeddings=[query_emb],
        n_results=min(top_k, count),
    )

    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    if not documents or not documents[0]:
        return {}

    docs = documents[0]
    metadatas = metadatas[0] if metadatas else []

    # Cross-encoder reranking
    reranker = get_reranker()
    if not reranker:
        return {}  # Graceful fallback could just return bi-encoder scores, but returning empty defaults to heuristics
        
    pairs    = [(jd_text, doc) for doc in docs]
    scores   = reranker.predict(pairs)

    # Aggregate: best chunk score per candidate
    candidate_scores: dict[str, float] = {}
    for meta, score in zip(metadatas, scores):
        cid = meta.get("candidate_id") if isinstance(meta, dict) else None
        if not cid:
            continue
        candidate_scores[cid] = max(
            candidate_scores.get(cid, float("-inf")),
            float(score)
        )

    # Normalise scores to [0, 1] using min-max scaling
    if len(candidate_scores) > 1:
        vals    = list(candidate_scores.values())
        min_v   = min(vals)
        max_v   = max(vals)
        rng     = max_v - min_v if max_v != min_v else 1.0
        candidate_scores = {
            cid: round((s - min_v) / rng, 4)
            for cid, s in candidate_scores.items()
        }

    return candidate_scores
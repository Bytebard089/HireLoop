import re
import chromadb
import os

CHROMA_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_store")
_client   = None
_embedder = None


def _rag_enabled() -> bool:
    return os.getenv("RAG_ENABLED", "0") == "1"


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def chunk_resume(resume_text: str) -> list[str]:
    """
    Split resume into 3 semantic chunks:
      0 = header (name, title, contact, summary)
      1 = experience (all work history)
      2 = skills + education
    """
    text = re.sub(r'\s+', ' ', resume_text).strip()

    # Heuristic: split on common section headings
    sections = re.split(
        r'\b(experience|work history|employment|skills|education|projects)\b',
        text,
        flags=re.IGNORECASE,
    )

    if len(sections) >= 5:
        header     = sections[0][:600]
        experience = ' '.join(sections[1:4])[:800]
        rest       = ' '.join(sections[4:])[:600]
    else:
        # Fallback: split by character count
        third = len(text) // 3
        header     = text[:third]
        experience = text[third:2*third]
        rest       = text[2*third:]

    return [header.strip(), experience.strip(), rest.strip()]


def embed_resume(candidate_id: str, resume_text: str, jd_id: str):
    """
    Embed a single resume into ChromaDB under collection jd_{jd_id}.
    Safe to call multiple times — upserts by ID.
    """
    if not _rag_enabled():
        return

    col      = get_client().get_or_create_collection(f"jd_{jd_id}")
    embedder = get_embedder()
    chunks   = chunk_resume(resume_text)
    vectors  = embedder.encode(chunks).tolist()

    col.upsert(
        documents=chunks,
        embeddings=vectors,
        metadatas=[
            {"candidate_id": candidate_id, "chunk_index": i, "chunk_type": t}
            for i, t in enumerate(["header", "experience", "skills"])
        ],
        ids=[f"{candidate_id}_chunk_{i}" for i in range(3)],
    )


def delete_resume(candidate_id: str, jd_id: str):
    col = get_client().get_or_create_collection(f"jd_{jd_id}")
    col.delete(ids=[f"{candidate_id}_chunk_{i}" for i in range(3)])
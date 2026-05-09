"""
Run once: python db/seed.py
Inserts 3 JDs + 50 realistic candidates into the database.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.models import init_db, get_session, JobDescription, Candidate
from ml.features import compute_features


def _seed_embedding_enabled() -> bool:
    return os.getenv("SEED_WITH_EMBEDDINGS", "0") == "1"

JOBS = [
    {
        "id": "jd-frontend-001",
        "raw_text": "Senior Frontend Engineer — 3+ years of React and TypeScript required. GraphQL, accessibility (WCAG), and performance optimisation experience strongly preferred. Remote-first, fast-shipping team.",
        "criteria": {"skills": ["react","typescript","graphql"], "exp_years": 3, "level": "senior", "keywords": ["accessibility","performance","wcag"]},
    },
    {
        "id": "jd-ml-001",
        "raw_text": "ML Engineer — 2+ years experience. Proficiency in Python, PyTorch or TensorFlow, and deploying models to production. Experience with LLMs, RAG pipelines, and MLOps a strong plus.",
        "criteria": {"skills": ["python","pytorch","tensorflow"], "exp_years": 2, "level": "mid", "keywords": ["llm","rag","mlops","production"]},
    },
]

CANDIDATES = [
    # JD: frontend
    {"jd_id": "jd-frontend-001", "name": "Arjun Mehta",    "resume_text": "Arjun Mehta | Senior Frontend Engineer | 5 years experience | React TypeScript GraphQL AWS Node.js | Razorpay 2yr Swiggy 2yr | Built design system used by 40 engineers | WCAG 2.1 accessibility audit contributor"},
    {"jd_id": "jd-frontend-001", "name": "Priya Sharma",   "resume_text": "Priya Sharma | Frontend Developer | 4 years | React TypeScript REST APIs | Works at Flipkart | Performance optimisation expert | reduced LCP by 40%"},
    {"jd_id": "jd-frontend-001", "name": "Rohan Das",      "resume_text": "Rohan Das | Frontend Engineer | 3 years | Vue.js JavaScript some React | MERN stack | currently at startup"},
    {"jd_id": "jd-frontend-001", "name": "Sneha Iyer",     "resume_text": "Sneha Iyer | Engineer | 6 years | Angular TypeScript Node.js | Backend heavy role | Express REST | SQL PostgreSQL"},
    {"jd_id": "jd-frontend-001", "name": "Vikram Nair",    "resume_text": "Vikram Nair | React Developer | 2 years | React JavaScript | Fresher to mid | small startup experience | basic CSS HTML"},
    {"jd_id": "jd-frontend-001", "name": "Ananya Roy",     "resume_text": "Ananya Roy | UI Engineer | 4 years | React TypeScript GraphQL | Apollo Client | Netflix design system contributor | WCAG expert | 3+ years accessibility"},
    {"jd_id": "jd-frontend-001", "name": "Karan Singh",    "resume_text": "Karan Singh | Full Stack | 5 years | React Node.js TypeScript | micro-frontends | webpack optimization | shipped 3 products"},
    {"jd_id": "jd-frontend-001", "name": "Deepa Menon",    "resume_text": "Deepa Menon | Frontend | 1 year | HTML CSS JavaScript React basics | bootcamp graduate | eager learner"},
    {"jd_id": "jd-frontend-001", "name": "Aakash Gupta",   "resume_text": "Aakash Gupta | Senior Engineer | 7 years | React TypeScript | GraphQL subscriptions | real-time dashboards | WebSocket | accessibility champion"},
    {"jd_id": "jd-frontend-001", "name": "Meera Krishnan", "resume_text": "Meera Krishnan | Frontend Architect | 8 years | React TypeScript | Design tokens | Component libraries | GraphQL | WCAG | Performance budgets | Core Web Vitals expert"},
    # JD: ml
    {"jd_id": "jd-ml-001", "name": "Rahul Verma",     "resume_text": "Rahul Verma | ML Engineer | 3 years | Python PyTorch scikit-learn | NLP transformers | deployed 4 models to production | AWS SageMaker | MLflow | RAG pipeline contributor"},
    {"jd_id": "jd-ml-001", "name": "Siddharth Kumar",  "resume_text": "Siddharth Kumar | Data Scientist | 2 years | Python TensorFlow pandas | Kaggle competitions | some production experience | Docker basics"},
    {"jd_id": "jd-ml-001", "name": "Lakshmi Narayan", "resume_text": "Lakshmi Narayan | AI Engineer | 4 years | Python PyTorch LLMs LangChain RAG | built internal GPT Q&A tool | MLOps CI/CD for models | Kubernetes"},
    {"jd_id": "jd-ml-001", "name": "Pooja Desai",     "resume_text": "Pooja Desai | Research Engineer | 3 years | Python PyTorch | published 2 papers NLP | good theory | limited production deployment experience"},
    {"jd_id": "jd-ml-001", "name": "Manish Tiwari",   "resume_text": "Manish Tiwari | Backend Engineer | 5 years | Java Python | REST APIs | no ML production experience | some pandas notebooks"},
]


def run_seed():
    init_db()
    from ml.dataset import generate as gen_dataset
    from ml.trainer import train_initial_model

    do_embed = _seed_embedding_enabled()
    embed_resume = None
    if do_embed:
        # Lazy import to avoid loading heavy native deps during basic DB seeding.
        from rag.embedder import embed_resume as _embed_resume
        embed_resume = _embed_resume

    gen_dataset()
    train_initial_model()

    with get_session() as session:
        for jd_data in JOBS:
            existing = session.get(JobDescription, jd_data["id"])
            if existing:
                continue
            jd = JobDescription(
                id=jd_data["id"],
                raw_text=jd_data["raw_text"],
                criteria=jd_data["criteria"],
            )
            session.add(jd)

        for c_data in CANDIDATES:
            cand = Candidate(
                jd_id=c_data["jd_id"],
                name=c_data["name"],
                resume_text=c_data["resume_text"],
                features=compute_features(
                    resume_text=c_data["resume_text"],
                    criteria=next(j["criteria"] for j in JOBS if j["id"] == c_data["jd_id"]),
                    semantic_sim=0.5,  # placeholder — will be updated on first score run
                ),
            )
            session.add(cand)
            session.flush()  # get ID before embedding
            if do_embed and embed_resume is not None:
                embed_resume(str(cand.id), cand.resume_text, c_data["jd_id"])

        session.commit()
    print(f"[seed] Inserted {len(JOBS)} JDs and {len(CANDIDATES)} candidates.")
    if not do_embed:
        print("[seed] Skipped embedding generation (set SEED_WITH_EMBEDDINGS=1 to enable).")


if __name__ == "__main__":
    run_seed()
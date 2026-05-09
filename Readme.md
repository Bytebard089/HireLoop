# HireLoop — Autonomous AI Recruiting Co-Pilot

> An AI agent that reads a job description, scores candidates using ML, generates adaptive interview questions, and **re-learns your preferences from every approve/reject decision in real time.**

**[Live Demo →](https://hireloop.vercel.app)** · **[Demo Video →](#)**

---

## What makes this different

Most ATS tools do keyword matching. HireLoop does three things they don't:

1. **Semantic scoring** — A LangGraph agent pipeline embeds each resume into ChromaDB, retrieves the most JD-relevant chunks via cross-encoder reranking, and feeds 4 engineered features into an XGBoost classifier.

2. **Adaptive re-ranking** — Every approve/reject decision is stored and appended to the XGBoost training set. Every 5 decisions, the model re-fits on the union of seed data + your feedback. Rankings re-sort live with a flash animation. The system literally learns what *you* value.

3. **Explainable AI** — Every score is broken down into 4 interpretable features (skill overlap, semantic similarity, experience gap, keyword density). The "Criteria Drift" panel shows how your XGBoost feature importances shift over model versions — you can watch the model adapt in real time.

---

## Architecture

```
React (Vercel)
    │
    │  REST / JSON
    ▼
Flask API (Render)
    │
    ▼
LangGraph Pipeline
 ├── jd_parser       — LLM extracts structured criteria (JSON mode)
 ├── resume_scorer   — 4 features + XGBoost.predict_proba → fit_score
 ├── question_gen    — Per-candidate gap analysis → 3 targeted questions
 ├── feedback_handler — Writes approve/reject, checks retrain threshold
 └── retrainer       — XGBoost.fit(seed + feedback), updates all ranks
    │
    ├── ChromaDB      — Resume chunks (bi-encoder + cross-encoder rerank)
    ├── PostgreSQL    — Candidates, feedback, model versions (Neon)
    └── XGBoost       — model.pkl retrained on every 5th feedback decision
```

### Data flow

```
JD text → jd_parser (LLM) → criteria dict
                                  │
Resumes → embed (MiniLM) → ChromaDB
                                  │
                          cross-encoder rerank
                                  │
                          compute_features()
                           ├── skill_overlap   (Jaccard)
                           ├── semantic_sim    (cross-encoder score)
                           ├── exp_gap         (normalised abs diff)
                           └── keyword_density (fraction of JD terms)
                                  │
                          XGBoost.predict_proba → fit_score
                                  │
                          ranked list → frontend
                                  │
                    [approve/reject] → feedback table
                                  │
                    feedback_count % 5 == 0 → retrainer
                                  │
                    XGBoost.fit(seed_200 + feedback_N)
                                  │
                    new importances → CriteriaDrift panel
                    new scores     → re-sorted ranking (flash animation)
```

---

## ML Pipeline

| Feature | How it's computed | Why it matters |
|---|---|---|
| `skill_overlap` | Jaccard(resume_skills ∩ jd_skills, jd_skills) | Direct requirement match |
| `semantic_sim` | cross-encoder/ms-marco-MiniLM-L-6-v2 score, normalised | Captures paraphrase / related skills. **Requires `RAG_ENABLED=1`** (defaults to 0 to avoid 500MB model load on cold start — set `RAG_ENABLED=1` in `.env` to enable) |
| `exp_gap` | abs(resume_years − jd_years) / 10, clipped [0,1] | Seniority alignment |
| `keyword_density` | count(jd_keywords in resume) / len(jd_keywords) | Domain vocabulary match |

**Initial training:** 200 synthetic labelled pairs (100 positive, 100 negative) with realistic noise — some overqualified candidates labelled negative, some borderline positives. This ensures the model isn't trivially separable from day one.

**Model evaluation:** `trainer.py` runs a stratified 80/20 split and 5-fold cross-validated AUC before final deployment fit. Sample output:
```
[trainer] Val AUC:  0.9712
[trainer] CV AUC:   0.9680 ± 0.0142
              precision  recall  f1-score
    reject       0.97      0.94      0.95
   approve       0.94      0.97      0.95
```

**Online retraining:** `xgb.XGBClassifier.fit(seed_df + feedback_df)`. Re-runs every 5 decisions. Seed data is always included to prevent catastrophic forgetting. Feature importances and `val_auc` are persisted per model version so you can inspect the full adaptation history.

---

## RAG Pipeline

1. **Chunking** — Each resume split into 3 semantic chunks: header (name/title/summary), experience (all job entries), skills+education.
2. **Embedding** — `all-MiniLM-L6-v2` (384-dim). Stored in ChromaDB with `candidate_id` + `chunk_type` metadata. One collection per JD to prevent cross-role pollution.
3. **Retrieval** — JD text embedded as query. Top-20 chunks retrieved by cosine similarity.
4. **Reranking** — `cross-encoder/ms-marco-MiniLM-L-6-v2` rescores all 20 pairs. Best score per candidate is min-max normalised → `semantic_sim` feature.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Type safety, fast HMR |
| State | Zustand | Minimal boilerplate, works perfectly with rank animation |
| Charts | Recharts | Zero-config, good TypeScript types |
| Backend | Flask + SQLAlchemy | Lightweight, easy Render deploy |
| AI orchestration | LangGraph | Stateful agent loops, conditional edges |
| LLM | GPT-4o-mini | JSON mode, cheap, fast |
| ML | XGBoost | Interpretable, fast refit, feature importances |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | Free, runs locally, no API cost |
| Vector store | ChromaDB (persistent) | Simple, file-based, zero infra |
| Database | PostgreSQL via Neon | Serverless free tier, SQLAlchemy ORM |
| Deploy | Vercel (frontend) + Render (backend) | Free tier, GitHub auto-deploy |

---

## Local Setup

### Prerequisites
- Python 3.11 or 3.12 (recommended for best package compatibility)
- Node.js 18+
- OpenAI API key
- PostgreSQL (or use SQLite for local dev — it auto-falls back)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: add OPENAI_API_KEY
# DATABASE_URL defaults to SQLite if not set

python -m ml.dataset    # generate 200-row seed dataset
python -m ml.trainer    # train initial XGBoost model
python -m db.seed       # create tables + insert demo candidates (fast seed, no embeddings)

# Optional: also generate embeddings during seeding (slower, heavier dependencies)
# SEED_WITH_EMBEDDINGS=1 python -m db.seed

python app.py           # starts on http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
# No .env needed for local dev — Vite proxies /api to localhost:5000
npm run dev             # starts on http://localhost:5173
```

Open `http://localhost:5173`. The seeded data (15 candidates across 2 JDs) is ready to demo immediately.

---

## Demo Script (90 seconds)

1. **Open** `http://localhost:5173`. Paste any job description → click "Parse JD". Show the extracted criteria card.

2. **Upload** 5–10 resume text files → click "Score resumes". Watch the ranked list appear with fit scores.

3. **Dashboard** — point out: rank badges, score bars, rank delta column (all `—` for now).

4. **Click candidate #1** → show the "Why this score?" panel with 4 feature bars. Show matched/missing skills.

5. **Switch to "Questions" tab** — show 3 adaptive questions generated from this candidate's specific gaps.

6. **Give feedback** — approve #1, #3, reject #2, #4. On the 5th decision, watch:
   - The "Criteria Drift" bar chart update live
   - The ranking re-sort with green/red flash animation
   - The "model v2" badge appear in the top nav

7. **Point at the drift panel** — "Skill overlap jumped from 40% to 58% because every candidate I approved had strong skill overlap. The model learned my preference without me configuring anything."

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jd/parse` | Parse JD text → structured criteria |
| `POST` | `/api/candidates/upload` | Upload resumes (PDF/TXT), score + rank |
| `GET`  | `/api/candidates/?jd_id=` | List ranked candidates for a JD |
| `GET`  | `/api/candidates/:id/questions?jd_id=` | Adaptive interview questions |
| `POST` | `/api/feedback/` | Submit approve/reject decision |
| `POST` | `/api/model/retrain` | Force retrain (any time) |
| `GET`  | `/api/model/importances/:jd_id` | Feature importances + version history |
| `GET`  | `/health` | Health check (used by Render) |

---

## Database Schema

```sql
job_descriptions   (id, raw_text, criteria JSONB, created_at)
candidates         (id, jd_id, name, resume_text, features JSONB,
                    fit_score, rank, prev_rank, created_at)
feedback           (id, jd_id, candidate_id, decision, created_at)
model_versions     (id, jd_id, version, importances JSONB,
                    feedback_count, model_path, created_at)
```

The `prev_rank` column is the entire basis of the rank-change animation — it stores the rank before each retrain so the frontend can compute `rank_change = prev_rank - new_rank` and trigger the CSS flash.

---

## Deployment

### Backend → Render

1. Push `backend/` to GitHub
2. New Web Service → connect repo → set root to `backend/`
3. Add env vars: `OPENAI_API_KEY`, `DATABASE_URL` (Neon), `FRONTEND_URL`
4. `render.yaml` is already configured — build + start commands are set

### Frontend → Vercel

1. Push `frontend/` to GitHub
2. New Project → connect repo → framework: Vite
3. Add env var: `VITE_API_URL=https://your-render-url.onrender.com/api`
4. Deploy

### Database → Neon

1. Create free project at `neon.tech`
2. Copy the connection string → paste as `DATABASE_URL` in Render env vars
3. Tables are auto-created on first `python app.py` startup via `init_db()`

---

## Project Structure

```
hireloop/
├── backend/
│   ├── app.py                    # Flask entry point
│   ├── render.yaml               # Render deployment config
│   ├── requirements.txt
│   ├── agents/
│   │   ├── graph.py              # LangGraph: scoring + feedback graphs
│   │   ├── state.py              # TypedDict shared state
│   │   └── nodes/
│   │       ├── jd_parser.py      # LLM → structured criteria
│   │       ├── resume_scorer.py  # Features + XGBoost inference
│   │       ├── question_gen.py   # Adaptive interview questions
│   │       ├── feedback_handler.py
│   │       └── retrainer.py      # XGBoost refit + re-rank
│   ├── ml/
│   │   ├── features.py           # 4-feature engineering
│   │   ├── trainer.py            # Initial model training
│   │   ├── dataset.py            # Synthetic seed data generation
│   │   └── model.pkl             # Persisted model (gitignored)
│   ├── rag/
│   │   ├── embedder.py           # Chunk + embed resumes → ChromaDB
│   │   └── retriever.py          # Bi-encoder + cross-encoder pipeline
│   ├── db/
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   └── seed.py               # Demo data seeder
│   └── api/routes/
│       ├── candidates.py         # JD + candidate endpoints
│       └── feedback.py           # Feedback + model endpoints
│
└── frontend/
    ├── src/
    │   ├── App.tsx               # Routing + top nav
    │   ├── types/index.ts        # Shared TypeScript types
    │   ├── api/client.ts         # All backend API calls
    │   ├── store/useStore.ts     # Zustand global state
    │   ├── pages/
    │   │   ├── JDInput.tsx       # Step 1: paste JD + upload resumes
    │   │   ├── Dashboard.tsx     # Ranked list + criteria drift panel
    │   │   └── CandidateDetail.tsx # Full detail + feedback
    │   └── components/
    │       ├── ScoreCard.tsx     # Candidate row + rank flash animation
    │       ├── CriteriaDrift.tsx # THE wow panel — live feature importance chart
    │       ├── WhyPanel.tsx      # Per-candidate score breakdown
    │       ├── AdaptiveQs.tsx    # Interview questions with skeleton loader
    │       └── FeedbackButtons.tsx # Approve/reject with optimistic update
    ├── vercel.json
    └── vite.config.ts
```

---

## What I learned / What I'd do differently

**Deliberate trade-offs:**
- Chose **dual-modality scoring** (RAG semantic + XGBoost ML) over pure LLM scoring because it gives interpretable feature importances — crucial for the adaptation loop. A single LLM score is a black box that can't drift.
- Used **ChromaDB per-JD collections** (not one shared collection) to prevent embedding space pollution between unrelated roles. A software engineer JD and a designer JD have completely different semantic clusters.
- Kept the **XGBoost retraining simple** (full refit, not online learning) because at <200 rows it's faster than incremental updates and avoids stability issues.

**What I'd build next:**
- Resume parser that handles messy PDFs properly (right now it relies on clean text)
- Multi-user support with per-user model personalisation
- A/B test mode — show two rankings (seed model vs adapted model) side-by-side
- Slack integration to submit feedback directly from a candidate message

---
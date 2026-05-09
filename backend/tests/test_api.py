"""
API integration tests for HireLoop Flask routes.
Run: pytest tests/ -v
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Use SQLite in-memory for tests — override before importing app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RAG_ENABLED",   "0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")   # prevents RuntimeError on import


@pytest.fixture(scope="session")
def client():
    """Flask test client with in-memory SQLite database."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# JD Parse — input validation
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_jd_missing_body(client):
    res = client.post("/api/jd/parse",
                      data=json.dumps({}),
                      content_type="application/json")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_parse_jd_empty_text(client):
    res = client.post("/api/jd/parse",
                      data=json.dumps({"jd_text": "   "}),
                      content_type="application/json")
    assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Candidates — input validation
# ─────────────────────────────────────────────────────────────────────────────

def test_upload_missing_jd_id(client):
    res = client.post("/api/candidates/upload",
                      data=json.dumps({"resumes": [{"name": "A", "text": "some text"}]}),
                      content_type="application/json")
    assert res.status_code == 400


def test_upload_no_resumes(client):
    res = client.post("/api/candidates/upload",
                      data=json.dumps({"jd_id": "fake-id", "resumes": []}),
                      content_type="application/json")
    assert res.status_code == 400


def test_list_candidates_missing_jd_id(client):
    res = client.get("/api/candidates/")
    assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Feedback — input validation
# ─────────────────────────────────────────────────────────────────────────────

def test_feedback_invalid_decision(client):
    res = client.post("/api/feedback/",
                      data=json.dumps({
                          "jd_id": "x",
                          "candidate_id": "y",
                          "decision": "maybe",
                      }),
                      content_type="application/json")
    assert res.status_code == 400
    assert "decision" in res.get_json().get("error", "")


def test_feedback_missing_fields(client):
    res = client.post("/api/feedback/",
                      data=json.dumps({"jd_id": "x"}),
                      content_type="application/json")
    assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 404 handler
# ─────────────────────────────────────────────────────────────────────────────

def test_404_handler(client):
    res = client.get("/api/nonexistent-route")
    assert res.status_code == 404
    data = res.get_json()
    assert "error" in data

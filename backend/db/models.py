import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Text, Float, Integer,
    DateTime, ForeignKey, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hireloop.db")

# SQLite compat: replace postgresql UUID + JSONB with compatible types
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import String as UUID        # noqa
    from sqlalchemy import JSON as JSONB         # noqa

engine_kwargs = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    })

engine  = create_engine(DATABASE_URL, **engine_kwargs)
Session = sessionmaker(bind=engine)
Base    = declarative_base()


@contextmanager
def get_session():
    session = Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _uuid():
    return str(uuid.uuid4())


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id         = Column(String(36), primary_key=True, default=_uuid)
    raw_text   = Column(Text,    nullable=False)
    criteria   = Column(JSONB,   nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    candidates = relationship("Candidate",  back_populates="jd", cascade="all, delete")
    feedbacks  = relationship("Feedback",   back_populates="jd", cascade="all, delete")
    versions   = relationship("ModelVersion", back_populates="jd", cascade="all, delete")


class Candidate(Base):
    __tablename__ = "candidates"

    id          = Column(String(36), primary_key=True, default=_uuid)
    jd_id       = Column(String(36), ForeignKey("job_descriptions.id"), nullable=False)
    name        = Column(String(200))
    resume_text = Column(Text, nullable=False)
    features    = Column(JSONB)          # {skill_overlap, semantic_sim, exp_gap, keyword_density, ...}
    fit_score   = Column(Float)
    rank        = Column(Integer)
    prev_rank   = Column(Integer)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    jd       = relationship("JobDescription", back_populates="candidates")
    feedback = relationship("Feedback", back_populates="candidate", cascade="all, delete")


class Feedback(Base):
    __tablename__ = "feedback"

    id           = Column(String(36), primary_key=True, default=_uuid)
    jd_id        = Column(String(36), ForeignKey("job_descriptions.id"), nullable=False)
    candidate_id = Column(String(36), ForeignKey("candidates.id"),       nullable=False)
    decision     = Column(String(10), nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("decision IN ('approve', 'reject')", name="ck_decision"),
    )

    jd        = relationship("JobDescription", back_populates="feedbacks")
    candidate = relationship("Candidate",       back_populates="feedback")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id             = Column(String(36), primary_key=True, default=_uuid)
    jd_id          = Column(String(36), ForeignKey("job_descriptions.id"), nullable=False)
    version        = Column(Integer, nullable=False)
    importances    = Column(JSONB)    # {feature: weight}
    feedback_count = Column(Integer, default=0)
    model_path     = Column(String(500))
    val_auc        = Column(Float, nullable=True)   # held-out AUC at training time
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    jd = relationship("JobDescription", back_populates="versions")


def init_db():
    Base.metadata.create_all(bind=engine)
    print("[db] Tables created.")
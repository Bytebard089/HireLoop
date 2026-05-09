import json
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.state import HireLoopState
from db.models import JobDescription, get_session

_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Set it in your environment or .env file.")

        # Groq exposes an OpenAI-compatible API surface.
        if api_key.startswith("gsk_"):
            groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
            _llm = ChatOpenAI(
                model=groq_model,
                temperature=0,
                openai_api_key=api_key,
                openai_api_base="https://api.groq.com/openai/v1",
            )
        else:
            _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)
    return _llm

SYSTEM = """You are a technical recruiter. Extract structured hiring criteria from job descriptions.
Return ONLY valid JSON — no markdown, no explanation.
Schema:
{
  "skills": ["React", "TypeScript"],       // required technical skills
  "exp_years": 3,                          // minimum years experience (int)
  "level": "senior",                       // junior | mid | senior | staff
  "keywords": ["GraphQL", "accessibility"] // important keywords beyond skills
}"""


def _fallback_criteria(jd_text: str) -> dict:
    text = jd_text or ""
    lower = text.lower()

    def _clean_item(x: str) -> str:
        x = x.strip().strip("-•")
        x = re.sub(r"\s+", " ", x)
        return x

    def _split_items(raw: str) -> list[str]:
        if not raw:
            return []
        # Split on commas only at top-level (outside parentheses).
        chunks = []
        buf = []
        depth = 0
        for ch in raw:
            if ch == "(":
                depth += 1
                buf.append(ch)
                continue
            if ch == ")":
                depth = max(0, depth - 1)
                buf.append(ch)
                continue
            if ch == "," and depth == 0:
                chunks.append("".join(buf))
                buf = []
                continue
            buf.append(ch)
        if buf:
            chunks.append("".join(buf))

        parts = []
        for chunk in chunks:
            p = _clean_item(chunk)
            if p:
                parts.append(p)
        return parts

    def _expand_parenthetical(items: list[str]) -> list[str]:
        out: list[str] = []
        for item in items:
            out.append(item)
            m = re.search(r"\((.*?)\)", item)
            if m:
                out.extend(_split_items(m.group(1)))
        return out

    def _uniq_case(items: list[str]) -> list[str]:
        seen = set()
        out = []
        for i in items:
            key = i.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
        return out

    required_match = re.search(r"required\s*:\s*(.+?)(?:\n|$)", text, flags=re.IGNORECASE)
    nice_match = re.search(r"nice\s*to\s*have\s*:\s*(.+?)(?:\n|$)", text, flags=re.IGNORECASE)

    required_items = _split_items(required_match.group(1)) if required_match else []
    nice_items = _split_items(nice_match.group(1)) if nice_match else []

    required_items = _uniq_case(_expand_parenthetical(required_items))
    nice_items = _uniq_case(_expand_parenthetical(nice_items))

    known_skills = [
        "react", "typescript", "javascript", "node", "python", "sql", "postgresql",
        "graphql", "aws", "docker", "kubernetes", "pytorch", "tensorflow",
    ]
    skills = [s for s in known_skills if s in lower]

    years_match = re.search(r"(\d+)\s*\+?\s*(years|yrs|year)", lower)
    exp_years = int(years_match.group(1)) if years_match else 0

    if "staff" in lower:
        level = "staff"
    elif "senior" in lower:
        level = "senior"
    elif "junior" in lower:
        level = "junior"
    else:
        level = "mid"

    keyword_candidates = [
        "accessibility", "performance", "wcag", "mlops", "rag", "llm",
        "microservices", "scalability", "distributed systems",
    ]
    keywords = [k for k in keyword_candidates if k in lower]

    # Prefer explicit sections when present.
    if required_items:
        skills = required_items
    if nice_items:
        keywords = nice_items

    if required_items:
        formatted_skills = skills
    else:
        formatted_skills = [s.title() if s.lower() != "aws" else "AWS" for s in skills]

    return {
        "skills": formatted_skills,
        "exp_years": exp_years,
        "level": level,
        "keywords": keywords,
    }


def jd_parser_node(state: HireLoopState) -> HireLoopState:
    """Parses raw JD text → structured criteria dict. Saves to DB."""
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Job Description:\n\n{state['jd_text']}")
    ]

    try:
        response = _get_llm().invoke(messages)
        try:
            criteria = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: extract JSON block if LLM added surrounding text.
            match = re.search(r'\{.*\}', response.content, re.DOTALL)
            criteria = json.loads(match.group()) if match else _fallback_criteria(state["jd_text"])
    except Exception as e:
        print(f"[jd_parser] LLM unavailable, using fallback parser: {e}")
        criteria = _fallback_criteria(state["jd_text"])

    # Persist to DB
    with get_session() as session:
        jd = session.get(JobDescription, state["jd_id"])
        if jd:
            jd.criteria = criteria
            session.commit()

    return {**state, "criteria": criteria}
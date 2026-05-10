import json
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.state import HireLoopState

_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Set it in your environment or .env file.")

        if api_key.startswith("gsk_"):
            groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
            _llm = ChatOpenAI(
                model=groq_model,
                temperature=0.7,
                openai_api_key=api_key,
                openai_api_base="https://api.groq.com/openai/v1",
            )
        else:
            _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=api_key)
    return _llm

SYSTEM = """You are a senior technical interviewer. Given a candidate's resume and a job description's criteria,
identify skill GAPS and generate exactly 3 targeted interview questions.

Rules:
- Each question must target a specific gap or area needing depth verification
- Tag each question: "gap:<skill>" | "depth:<skill>" | "system_design"
- Questions must be concrete and specific — not generic "tell me about yourself"
- Return ONLY valid JSON:
[
  {"tag": "gap:GraphQL", "question": "Your resume doesn't mention GraphQL — how would you..."},
  {"tag": "depth:React", "question": "Walk me through how you'd optimise..."},
  {"tag": "system_design", "question": "The JD mentions high-traffic — describe..."}
]"""


def question_gen_node(state: HireLoopState) -> HireLoopState:
    """Generates 3 adaptive interview questions per candidate based on their specific gaps."""
    criteria   = state.get("criteria", {})
    questions  = {}

    for candidate in state.get("ranked", []):
        cid          = candidate["candidate_id"]
        features     = candidate["features"]

        # Build prompt — prefer experience section over header
        # The resume_snippet in features is the first 400 chars (usually header/contact).
        # We also include found/missing skills to give the LLM richer signal.
        resume_context = features.get("resume_snippet", "No summary available")
        # Try to find the experience section if it exists deeper in the text
        full_text = features.get("resume_snippet", "")  # kept for backward compat
        # Build a richer context block instead
        found    = ", ".join(features.get("found_skills",   [])) or "None identified"
        missing  = ", ".join(features.get("missing_skills", [])) or "None identified"
        exp_yrs  = features.get("resume_years", 0)

        user_msg = f"""Job Criteria:
Skills required: {', '.join(criteria.get('skills', []))}
Keywords: {', '.join(criteria.get('keywords', []))}
Level: {criteria.get('level', 'mid')}
Experience required: {criteria.get('exp_years', 0)} years

Candidate Summary:
Resume excerpt: {resume_context}
Years of experience detected: {exp_yrs}
Skills confirmed in resume: {found}
Skills NOT found in resume (gaps to probe): {missing}"""

        messages = [
            SystemMessage(content=SYSTEM),
            HumanMessage(content=user_msg),
        ]

        try:
            response = _get_llm().invoke(messages)
            text = response.content.strip()
            
            # Strip markdown code blocks if the LLM added them
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            try:
                qs = json.loads(text)
            except json.JSONDecodeError:
                # Handle stray surrounding text
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    qs = json.loads(match.group())
                else:
                    raise ValueError("No JSON array found in LLM response")
                    
            if not isinstance(qs, list):
                raise ValueError("LLM did not return a JSON array")
            questions[cid] = qs
        except Exception as e:
            print(f"Question gen failed: {e}")
            questions[cid] = [
                {"tag": "general", "question": "Walk me through your most complex frontend project."},
                {"tag": "general", "question": "How do you approach performance optimisation?"},
                {"tag": "general", "question": "Describe a time you had to make a difficult technical trade-off."},
            ]

    return {**state, "questions": questions}
import json
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.state import HireLoopState
from db.models import Candidate, get_session

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

SYSTEM = """You are a senior technical interviewer. Given a candidate's FULL resume and a job description's criteria,
perform a deep analysis and generate targeted output.

Your task:
1. Identify specific SKILL GAPS between the resume and the JD requirements
2. Identify areas where the candidate has RELEVANT experience that needs DEPTH verification
3. Generate exactly 3 targeted interview questions

Rules:
- Each question MUST reference specific details from THIS candidate's resume (projects, companies, technologies, years)
- Tag each question: "gap:<skill>" | "depth:<skill>" | "project:<project_name>" | "system_design"
- Questions must be concrete, specific, and personalized — NEVER generic
- Reference the candidate's actual projects, roles, and technologies when forming questions
- If the candidate mentions a project, ask about architecture decisions, trade-offs, or scaling challenges in that specific project
- If a required skill is missing, frame the question around how they'd bridge that gap given their existing experience

Return ONLY valid JSON — no markdown, no explanation:
{
  "skill_gaps": [
    {"skill": "GraphQL", "severity": "high", "context": "Resume shows REST API experience at Company X but no GraphQL mention"}
  ],
  "questions": [
    {"tag": "gap:GraphQL", "question": "Your work at Company X used REST APIs — how would you approach migrating to GraphQL?"},
    {"tag": "depth:React", "question": "You mention building a design system at Company Y — walk me through..."},
    {"tag": "project:ChatBot", "question": "Your AI chatbot project used LangChain — what retrieval strategy did you use?"}
  ]
}"""


def _extract_resume_sections(resume_text: str) -> dict:
    """Extract structured sections from a resume for richer LLM context."""
    text = resume_text or ""

    sections = {
        "projects": "",
        "experience": "",
        "skills_section": "",
        "education": "",
        "summary": "",
    }

    # Try to find experience section
    exp_match = re.search(
        r'\b(experience|work history|employment|professional background)\b(.{50,1500}?)(?=\b(projects?|skills?|education|certifications?)\b|\Z)',
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if exp_match:
        sections["experience"] = exp_match.group(2)[:1200].strip()

    # Try to find projects section
    proj_match = re.search(
        r'\b(projects?)\b(.{30,1200}?)(?=\b(skills?|education|certifications?|experience)\b|\Z)',
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if proj_match:
        sections["projects"] = proj_match.group(2)[:1000].strip()

    # Try to find skills section
    skills_match = re.search(
        r'\b(skills?|technologies|tech stack)\b(.{20,600}?)(?=\b(experience|projects?|education)\b|\Z)',
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if skills_match:
        sections["skills_section"] = skills_match.group(2)[:500].strip()

    # Summary / header (first 300 chars)
    sections["summary"] = text[:300].strip()

    return sections


def question_gen_node(state: HireLoopState) -> HireLoopState:
    """Generates 3 adaptive interview questions per candidate based on their specific resume content."""
    criteria   = state.get("criteria", {})
    questions  = {}

    # Load full resume texts from DB for all candidates being scored
    resume_texts = {}
    candidate_ids = [c["candidate_id"] for c in state.get("ranked", [])]
    if candidate_ids:
        with get_session() as session:
            for cid in candidate_ids:
                cand = session.get(Candidate, cid)
                if cand and cand.resume_text:
                    resume_texts[cid] = cand.resume_text

    for candidate in state.get("ranked", []):
        cid          = candidate["candidate_id"]
        features     = candidate["features"]

        # Get FULL resume text from DB, not just the truncated snippet
        full_resume = resume_texts.get(cid, features.get("resume_snippet", "No resume available"))
        resume_sections = _extract_resume_sections(full_resume)

        # Build rich context from features
        found    = ", ".join(features.get("found_skills",   [])) or "None identified"
        missing  = ", ".join(features.get("missing_skills", [])) or "None identified"
        exp_yrs  = features.get("resume_years", 0)

        # Truncate full resume to a reasonable size for the LLM (2000 chars)
        resume_for_llm = full_resume[:2000] if len(full_resume) > 2000 else full_resume

        user_msg = f"""Job Description Criteria:
Skills required: {', '.join(criteria.get('skills', []))}
Keywords/technologies: {', '.join(criteria.get('keywords', []))}
Level: {criteria.get('level', 'mid')}
Experience required: {criteria.get('exp_years', 0)} years

--- CANDIDATE'S FULL RESUME ---
{resume_for_llm}

--- PARSED RESUME ANALYSIS ---
Years of experience detected: {exp_yrs}
Skills CONFIRMED in resume: {found}
Skills NOT FOUND in resume (gaps): {missing}
Experience section: {resume_sections['experience'][:500] if resume_sections['experience'] else 'Not clearly delineated'}
Projects mentioned: {resume_sections['projects'][:500] if resume_sections['projects'] else 'None explicitly listed'}

Generate personalized skill gap analysis and interview questions for THIS specific candidate."""

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
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Handle stray surrounding text — try to find JSON object or array
                obj_match = re.search(r"\{.*\}", text, re.DOTALL)
                arr_match = re.search(r"\[.*\]", text, re.DOTALL)
                if obj_match:
                    parsed = json.loads(obj_match.group())
                elif arr_match:
                    # Backward compat: LLM returned just an array of questions
                    parsed = {"skill_gaps": [], "questions": json.loads(arr_match.group())}
                else:
                    raise ValueError("No JSON found in LLM response")

            # Handle both new format (dict with skill_gaps + questions) and legacy (array)
            if isinstance(parsed, list):
                # Legacy format: just an array of questions
                questions[cid] = {"skill_gaps": [], "questions": parsed}
            elif isinstance(parsed, dict):
                skill_gaps = parsed.get("skill_gaps", [])
                qs = parsed.get("questions", [])
                if not isinstance(qs, list):
                    qs = []
                questions[cid] = {"skill_gaps": skill_gaps, "questions": qs}
            else:
                raise ValueError("Unexpected LLM response format")

        except Exception as e:
            print(f"Question gen failed for {cid}: {e}")
            # Fallback: generate questions based on the features we DO have
            fallback_qs = []
            missing_list = features.get("missing_skills", [])
            if missing_list:
                fallback_qs.append({
                    "tag": f"gap:{missing_list[0]}",
                    "question": f"Your resume doesn't mention {missing_list[0]} — how would you approach learning and applying it in a production setting?"
                })
            if len(missing_list) > 1:
                fallback_qs.append({
                    "tag": f"gap:{missing_list[1]}",
                    "question": f"The role requires {missing_list[1]} experience. What's the closest technology you've worked with, and how would you bridge that gap?"
                })
            found_list = features.get("found_skills", [])
            if found_list:
                fallback_qs.append({
                    "tag": f"depth:{found_list[0]}",
                    "question": f"Walk me through the most complex challenge you've solved with {found_list[0]}."
                })
            # Fill remaining slots with contextual fallbacks
            while len(fallback_qs) < 3:
                fallback_qs.append({
                    "tag": "system_design",
                    "question": "Describe a system you've built end-to-end. What were the key architectural decisions and trade-offs?"
                })

            questions[cid] = {
                "skill_gaps": [{"skill": s, "severity": "unknown", "context": "Auto-detected gap"} for s in missing_list[:3]],
                "questions": fallback_qs[:3],
            }

    return {**state, "questions": questions}
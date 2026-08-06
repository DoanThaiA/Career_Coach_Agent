from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import EvaluationReport

WEIGHTS = {
    "skill": 0.40,
    "experience": 0.25,
    "education": 0.15,
    "qualitative": 0.20,
}

def aggregate_score_node(state: EvaluationState) -> dict:
    jd = state.get("jd_parsed")
    
    w_skill = WEIGHTS["skill"]
    w_exp = WEIGHTS["experience"]
    w_edu = WEIGHTS["education"]
    w_qual = WEIGHTS["qualitative"]
    
    if jd and (not jd.education_requirements or not jd.education_requirements.min_degree_level or jd.education_requirements.min_degree_level == "none"):
        w_skill += 0.10
        w_exp += 0.05
        w_edu = 0.0

    final = (
        state.get("skill_score", 0) * w_skill
        + state.get("experience_score", 0) * w_exp
        + state.get("education_score", 0) * w_edu
        + state.get("qualitative_score", 0) * w_qual
    )
    return {"final_score": round(final, 1)}

def _fit_level(score: float) -> str:
    if score >= 80:
        return "rất phù hợp"
    if score >= 60:
        return "khá phù hợp"
    if score >= 40:
        return "cần cải thiện thêm"
    return "chưa phù hợp với vị trí này"

def build_output_node(state: EvaluationState) -> dict:
    score = state.get("final_score", 0)
    
    breakdown = {
        "skill_score": state.get("skill_score", 0),
        "experience_score": state.get("experience_score", 0),
        "education_score": state.get("education_score", 0),
        "qualitative_score": state.get("qualitative_score", 0),
    }

    report = EvaluationReport(
        match_score=score,
        fit_level=_fit_level(score),
        breakdown=breakdown,
        matched_skills=state.get("matched_skills", []),
        missing_skills=state.get("missing_skills", []),
        missing_must_have_skills=state.get("missing_must_have_skills", []),
        overall_impression=state.get("overall_impression", ""),
        strengths=state.get("strengths", []),
        improvement_suggestions=state.get("improvement_suggestions", [])
    )

    return {"eval_report": report}

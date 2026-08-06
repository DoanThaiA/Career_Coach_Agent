from src.agents.evaluation_agent.state import EvaluationState

def score_experience_node(state: EvaluationState) -> dict:
    cv, jd = state.get("cv_parsed"), state.get("jd_parsed")
    min_years = jd.min_years_experience
    cv_years = cv.total_yoe or 0

    if not min_years:
        return {"experience_score": 100.0}

    score = 100.0 if cv_years >= min_years else round((cv_years / min_years) * 100, 1)
    return {"experience_score": score}

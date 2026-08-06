from src.agents.evaluation_agent.state import EvaluationState

def score_education_node(state: EvaluationState) -> dict:
    cv, jd = state.get("cv_parsed"), state.get("jd_parsed")
    edu_req = jd.education_requirements

    if not edu_req or not edu_req.min_degree_level:
        return {"education_score": 100.0}

    degree_rank = {"none": 0, "high_school": 1, "associate": 2, "bachelor": 3, "master": 4, "phd": 5}
    required_rank = degree_rank.get(edu_req.min_degree_level, 0)

    cv_max_rank = 0
    degree_keywords = {
        "phd": 5, "tiến sĩ": 5, "doctorate": 5,
        "master": 4, "thạc sĩ": 4, "m.s": 4, "msc": 4, "m.a": 4, "mba": 4,
        "bachelor": 3, "cử nhân": 3, "kỹ sư": 3, "b.s": 3, "bsc": 3, "b.a": 3,
        "associate": 2, "cao đẳng": 2,
    }
    for edu in cv.education:
        if not edu.degree:
            continue
        degree_lower = edu.degree.lower()
        for keyword, rank in degree_keywords.items():
            if keyword in degree_lower:
                cv_max_rank = max(cv_max_rank, rank)

    score = 100.0 if cv_max_rank >= required_rank else round((cv_max_rank / max(required_rank, 1)) * 100, 1)
    return {"education_score": score}

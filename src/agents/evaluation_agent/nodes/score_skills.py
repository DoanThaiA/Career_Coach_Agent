"""
score_skills_node: Đánh giá kỹ năng CV vs JD với thuật toán matching cải tiến.

Cải tiến so với phiên bản cũ:
- Thêm alias dictionary cho các công nghệ có nhiều tên (js/javascript, k8s/kubernetes...)
- Sử dụng token-set matching thay vì substring đơn thuần → tránh false positive
- Trọng số must_have=5, important=3, nice_to_have=1 (thay vì 3/2/1) → phản ánh đúng tầm quan trọng
"""
from src.agents.evaluation_agent.state import EvaluationState

# Alias dictionary: các tên phổ biến của cùng một công nghệ
_TECH_ALIASES: dict[str, set[str]] = {
    "javascript": {"js", "javascript", "ecmascript", "es6", "es2015"},
    "typescript": {"ts", "typescript"},
    "python": {"py", "python", "python3"},
    "kubernetes": {"k8s", "kubernetes"},
    "postgresql": {"postgres", "postgresql", "psql"},
    "mongodb": {"mongo", "mongodb"},
    "elasticsearch": {"es", "elasticsearch", "elastic"},
    "react": {"reactjs", "react.js", "react"},
    "vue": {"vuejs", "vue.js", "vue"},
    "angular": {"angularjs", "angular.js", "angular"},
    "nextjs": {"next.js", "nextjs", "next js"},
    "nodejs": {"node.js", "nodejs", "node js", "node"},
    "fastapi": {"fast api", "fastapi"},
    "django": {"django"},
    "flask": {"flask"},
    "springboot": {"spring boot", "springboot", "spring-boot"},
    "dotnet": {".net", "dotnet", "dot net", "asp.net"},
    "cicd": {"ci/cd", "ci cd", "cicd"},
    "mlops": {"ml ops", "mlops"},
    "llm": {"large language model", "llm", "llms"},
    "aws": {"aws", "amazon web services"},
    "gcp": {"gcp", "google cloud", "google cloud platform"},
    "azure": {"azure", "microsoft azure"},
    "mysql": {"mysql"},
    "redis": {"redis"},
    "kafka": {"apache kafka", "kafka"},
    "rabbitmq": {"rabbit mq", "rabbitmq"},
    "docker": {"docker"},
    "terraform": {"terraform"},
    "git": {"git", "github", "gitlab", "bitbucket"},
}

# Build reverse alias lookup: từ alias → canonical
_ALIAS_LOOKUP: dict[str, str] = {}
for canonical, aliases in _TECH_ALIASES.items():
    for alias in aliases:
        _ALIAS_LOOKUP[alias] = canonical


def _normalize_skill(skill_name: str) -> str:
    """Normalize tên skill về dạng canonical."""
    lower = skill_name.lower().strip()
    # Kiểm tra exact alias match
    if lower in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[lower]
    # Kiểm tra từng alias nếu tên có nhiều từ
    for alias, canonical in _ALIAS_LOOKUP.items():
        if alias in lower or lower in alias:
            # Chỉ accept nếu overlap đáng kể (tránh false positive ngắn)
            if len(alias) >= 3 and len(lower) >= 3:
                return canonical
    return lower


def _skills_match(req_skill: str, cv_skill: str) -> bool:
    """Kiểm tra xem 2 skill có match không với thuật toán cải tiến.
    
    Sử dụng token-set intersection thay vì substring để tránh false positive.
    Ví dụ: "C" sẽ KHÔNG match "C++"; "Docker" sẽ KHÔNG match "Docker Compose"
    trừ khi bên JD yêu cầu "Docker" thực sự.
    """
    req_norm = _normalize_skill(req_skill)
    cv_norm = _normalize_skill(cv_skill)

    # Exact match sau normalize
    if req_norm == cv_norm:
        return True

    # Chỉ token-set match nếu cả 2 đều dài hơn 3 chars để tránh false positive
    if len(req_norm) >= 4 and len(cv_norm) >= 4:
        req_tokens = set(req_norm.split())
        cv_tokens = set(cv_norm.split())
        # Overlap tốt: req là subset của cv hoặc cv là subset của req
        if req_tokens and cv_tokens:
            if req_tokens.issubset(cv_tokens) or cv_tokens.issubset(req_tokens):
                return True

    return False


def score_skills_node(state: EvaluationState) -> dict:
    cv, jd = state.get("cv_parsed"), state.get("jd_parsed")

    cv_skills_raw = cv.all_technologies()
    # Normalize tất cả CV skills
    cv_skills_normalized = {_normalize_skill(s) for s in cv_skills_raw}

    if not jd.skills or not jd.skills.all_skills():
        return {"skill_score": 100.0, "matched_skills": [], "missing_skills": [], "missing_must_have_skills": []}

    # Trọng số: must_have=5, important=3, nice_to_have=1
    weight_points = {"must_have": 5, "important": 3, "nice_to_have": 1}
    total_weight = 0
    earned_weight = 0
    matched, missing, missing_must_have = [], [], []

    for skill in jd.skills.all_skills():
        w = weight_points.get(skill.weight, 1)
        total_weight += w

        # Thử match với từng CV skill bằng thuật toán cải tiến
        is_matched = any(_skills_match(skill.name, cv_s) for cv_s in cv_skills_raw)

        if is_matched:
            earned_weight += w
            matched.append(skill.name)
        else:
            missing.append(skill.name)
            if skill.weight == "must_have":
                missing_must_have.append(skill.name)

    score = round((earned_weight / total_weight) * 100, 1) if total_weight else 100.0
    return {
        "skill_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "missing_must_have_skills": missing_must_have,
    }

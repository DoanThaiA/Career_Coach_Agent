from typing import TypedDict, Optional, Annotated, List
from operator import add

from src.agents.evaluation_agent.output_schema import EvaluationReport
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements


class EvaluationState(TypedDict, total=False):
    """State cho self-check evaluation agent graph."""
    # Input
    cv_parsed: Optional[CVInformation]
    jd_parsed: Optional[JDRequirements]
    
    errors: Annotated[List[str], add]

    skill_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    missing_must_have_skills: List[str]

    experience_score: float
    education_score: float

    qualitative_score: float
    overall_impression: str
    strengths: List[str]
    improvement_suggestions: List[dict]

    final_score: float
    
    # Output
    eval_report: Optional[EvaluationReport]
from typing import TypedDict, Optional, Annotated, List
from operator import add

from src.agents.evaluation_agent.output_schema import (
    SkillEvaluationResult,
    ExperienceEvaluationResult,
    EvaluationReport,
)
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements


class EvaluationState(TypedDict):
    """State cho evaluation agent graph.
    
    Flow: cv_content + job_requirement (raw text)
        → extract_cv → cv_parsed (CVInformation)
        → parse_jd → jd_parsed (JDRequirements)
        → evaluate → eval_report (EvaluationReport)
    """
    # Input
    cv_content: Optional[str]
    job_requirement: Optional[str]

    # Intermediate (structured data)
    cv_parsed: Optional[CVInformation]
    jd_parsed: Optional[JDRequirements]
    
    # Intermediate (evaluation results)
    skill_evaluation: Optional[SkillEvaluationResult]
    experience_evaluation: Optional[ExperienceEvaluationResult]

    # Output
    eval_report: Optional[EvaluationReport]

    # Error accumulator
    errors: Annotated[List[str], add]
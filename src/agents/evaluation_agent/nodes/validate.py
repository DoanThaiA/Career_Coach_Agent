from typing import Literal
from src.agents.evaluation_agent.state import EvaluationState
from src.core.logger import get_logger

logger = get_logger(__name__)

def validate_input(state: EvaluationState) -> dict:
    """Kiểm tra xem đầu vào đã có sẵn cv_parsed và jd_parsed chưa."""
    errors = state.get("errors") or []
    if not state.get("cv_parsed"):
        logger.warning("✖ Thiếu cv_parsed (schema CV)")
        errors.append("Thiếu cv_parsed (schema CV)")
    if not state.get("jd_parsed"):
        logger.warning("✖ Thiếu jd_parsed (schema JD)")
        errors.append("Thiếu jd_parsed (schema JD)")
        
    if errors:
        return {"errors": errors}
    return {}

def extraction_failed_node(state: EvaluationState) -> dict:
    # Not used if input is already parsed, but kept for completeness
    return {}

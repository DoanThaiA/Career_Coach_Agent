import json
from src.core.logger import get_logger
from src.utils import get_evaluation_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.evaluation_agent.prompt import EVAL_EXPERIENCE_PROMPT
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import ExperienceEvaluationResult

logger = get_logger(__name__)


def _filter_cv_for_experience(cv_parsed) -> str:
    """Chỉ gửi phần kinh nghiệm cho eval_experience (tiết kiệm token)."""
    filtered = {
        "work_experience": [
            exp.model_dump() for exp in (cv_parsed.work_experience or [])
        ],
        "total_yoe": cv_parsed.total_yoe,
    }
    return json.dumps(filtered, indent=2, ensure_ascii=False)


async def eval_experience_node(state: EvaluationState) -> dict:
    """Node đánh giá kinh nghiệm và đề xuất viết lại."""
    logger.info("▶ Bắt đầu xử lý eval_experience_node ...")
    
    cv_parsed = state.get("cv_parsed")
    jd_parsed = state.get("jd_parsed")
    
    if not cv_parsed or not jd_parsed:
        return {"errors": ["Thiếu cv_parsed hoặc jd_parsed để đánh giá kinh nghiệm."]}
        
    try:
        llm = get_evaluation_llm()
        prompt = EVAL_EXPERIENCE_PROMPT.format(
            cv_data=_filter_cv_for_experience(cv_parsed),
            jd_data=jd_parsed.model_dump_json(indent=2),
        ) + get_schema_instruction(ExperienceEvaluationResult)
        
        result = await generate_with_retry_and_correction(llm, prompt, ExperienceEvaluationResult, max_retries=3)
        logger.info("✔ Đánh giá kinh nghiệm thành công")
        return {"experience_evaluation": result}
    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý eval_experience_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi đánh giá kinh nghiệm: {str(e)}"]}

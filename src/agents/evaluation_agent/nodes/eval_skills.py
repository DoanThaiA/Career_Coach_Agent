import json
from src.core.logger import get_logger
from src.utils import get_evaluation_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.evaluation_agent.prompt import EVAL_SKILLS_PROMPT
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import SkillEvaluationResult

logger = get_logger(__name__)


def _filter_cv_for_skills(cv_parsed) -> str:
    """Chỉ gửi phần kỹ năng và kinh nghiệm cho eval_skills (tiết kiệm token)."""
    filtered = {
        "skills": cv_parsed.skills.model_dump() if cv_parsed.skills else None,
        "work_experience": [
            exp.model_dump() for exp in (cv_parsed.work_experience or [])
        ],
        "total_yoe": cv_parsed.total_yoe,
    }
    return json.dumps(filtered, indent=2, ensure_ascii=False)


async def eval_skills_node(state: EvaluationState) -> dict:
    """Node đánh giá kỹ năng của ứng viên."""
    logger.info("▶ Bắt đầu xử lý eval_skills_node ...")
    
    cv_parsed = state.get("cv_parsed")
    jd_parsed = state.get("jd_parsed")
    
    if not cv_parsed or not jd_parsed:
        return {"errors": ["Thiếu cv_parsed hoặc jd_parsed để đánh giá kỹ năng."]}
        
    try:
        llm = get_evaluation_llm()
        prompt = EVAL_SKILLS_PROMPT.format(
            cv_data=_filter_cv_for_skills(cv_parsed),
            jd_data=jd_parsed.model_dump_json(indent=2),
        ) + get_schema_instruction(SkillEvaluationResult)
        
        result = await generate_with_retry_and_correction(llm, prompt, SkillEvaluationResult, max_retries=3)
        logger.info("✔ Đánh giá kỹ năng thành công")
        return {"skill_evaluation": result}
    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý eval_skills_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi đánh giá kỹ năng: {str(e)}"]}

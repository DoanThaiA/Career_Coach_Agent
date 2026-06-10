from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.prompt import INTERVIEW_PLANNER_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import InterviewPlan
from src.core.logger import get_logger

logger = get_logger(__name__)

async def interview_plan(state: InterviewState) -> dict:
    """Node tạo đề cương phỏng vấn.
    
    Args:
        state: Trạng thái hiện tại, chứa jd_parsed và cv_parsed
        
    Returns:
        dict chứa topics (InterviewPlan) hoặc errors
    """
    logger.info(" Bắt đầu xử lý interview_plan_node ...")
    jd_parsed = state.get("jd_parsed")
    cv_parsed = state.get("cv_parsed")

    if not jd_parsed:
        logger.warning("✖ Không tìm thấy nội dung JD")
        return {"errors": ["Không tìm thấy nội dung JD (job_requirement)"]}

    if not cv_parsed:
        logger.warning("✖ Không tìm thấy nội dung CV")
        return {"errors": ["Không tìm thấy nội dung CV"]}
    
    try:
        llm = get_extraction_llm()
        
        prompt = INTERVIEW_PLANNER_PROMPT.format(
            cv_context=cv_parsed.model_dump_json(indent=2, ensure_ascii=False),
            jd_context=jd_parsed.model_dump_json(indent=2, ensure_ascii=False)
        ) + get_schema_instruction(InterviewPlan)
        
        result = await generate_with_retry_and_correction(llm, prompt, InterviewPlan, max_retries=3)

        if not result or not result.topics:
            logger.warning("✖ LLM không sinh được Topics hợp lệ")
            return {"errors": ["Không thể tạo danh sách chủ đề phỏng vấn từ dữ liệu đầu vào."]}
        
        topics = [topic.model_dump() for topic in result.topics]
        
        logger.info(f" Tạo đề cương phỏng vấn thành công với {len(topics)} chủ đề")
        return {
            "topics": topics,
            "current_topic_index": 0,
            "followup_count": 0
        }
    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý interview_plan_node: {e}")
        return {"errors": [f"Lỗi tạo đề cương phỏng vấn: {str(e)}"]}

    
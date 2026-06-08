from src.core.logger import get_logger
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.evaluation_agent.output_schema import JDRequirements
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.prompt import PARSE_JD_PROMPT

logger = get_logger(__name__)


async def parse_jd_node(state: EvaluationState) -> dict:
    """Node phân tích JD: text thô → JDRequirements (structured).
    
    Gọi LLM trực tiếp và parse JSON thủ công thay vì dùng
    with_structured_output (không tương thích LLM server local).
    """
    logger.info("▶ Bắt đầu xử lý parse_jd_node ...")
    job_requirement = state.get("job_requirement")

    if not job_requirement:
        logger.warning("✖ Không tìm thấy nội dung JD")
        return {"errors": ["Không tìm thấy nội dung JD (job_requirement)"]}

    if not job_requirement.strip():
        logger.warning("✖ Nội dung JD rỗng")
        return {"errors": ["Nội dung JD rỗng"]}

    try:
        llm = get_extraction_llm()
        prompt = PARSE_JD_PROMPT.format(jd_context=job_requirement) + get_schema_instruction(JDRequirements)
        # Sử dụng cơ chế self-correction
        jd_parsed = await generate_with_retry_and_correction(llm, prompt, JDRequirements, max_retries=3)

        must_have_count = sum(1 for s in jd_parsed.skills if s.priority.value == "must_have")
        nice_to_have_count = len(jd_parsed.skills) - must_have_count
        logger.info(
            f"✔ Parse JD thành công: {jd_parsed.job_title} | "
            f"Must-have: {must_have_count}, Nice-to-have: {nice_to_have_count}"
        )
        return {"jd_parsed": jd_parsed}

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý parse_jd_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi phân tích JD: {str(e)}"]}

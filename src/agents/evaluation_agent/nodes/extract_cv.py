from src.core.logger import get_logger
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.evaluation_agent.output_schema import CVInformation
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.prompt import EXTRACT_PROMPT

logger = get_logger(__name__)


async def extractor_node(state: EvaluationState) -> dict:
    """Node bóc tách CV: text thô → CVInformation (structured).
    
    Gọi LLM trực tiếp và parse JSON thủ công thay vì dùng
    with_structured_output (không tương thích LLM server local).
    """
    logger.info("▶ Bắt đầu xử lý extractor_node ...")
    cv_content = state.get("cv_content")

    if not cv_content:
        logger.warning("✖ Không tìm thấy nội dung CV")
        return {"errors": ["Không tìm thấy nội dung CV"]}

    if not cv_content.strip():
        logger.warning("✖ Nội dung CV rỗng")
        return {"errors": ["Nội dung CV rỗng"]}

    try:
        llm = get_extraction_llm()
        prompt = EXTRACT_PROMPT.format(cv_context=cv_content.model_dump_json(indent=2, ensure_ascii=False)) + get_schema_instruction(CVInformation)
        # Sử dụng cơ chế self-correction
        cv_parsed = await generate_with_retry_and_correction(llm, prompt, CVInformation, max_retries=3)

        # Validation cơ bản
        if not cv_parsed.work_experience and not cv_parsed.skills and not cv_parsed.education:
            logger.warning("⚠ CV được parse nhưng không có dữ liệu quan trọng")

        logger.info("✔ Xử lý extractor_node thành công")
        return {"cv_parsed": cv_parsed}

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi bóc tách CV: {str(e)}"]}
from src.core.logger import get_logger
from src.utils import get_extraction_llm
from src.agents.evaluation_agent.output_schema import CVInformation
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.prompt import EXTRACT_PROMPT
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(
        f"Retry extractor_node lần {retry_state.attempt_number}: {retry_state.outcome.exception()}"
    ),
)
async def _extract_with_retry(structured_llm, prompt: str) -> CVInformation:
    """Gọi LLM có retry với exponential backoff."""
    return await structured_llm.ainvoke(prompt)


def _get_schema_instruction(schema_class) -> str:
    """Tạo hướng dẫn JSON schema từ Pydantic model để LLM biết format cần trả."""
    import json
    schema = schema_class.model_json_schema()
    return (
        "\n\nHãy trả kết quả dưới dạng JSON hợp lệ theo đúng schema sau. "
        "CHỈ trả JSON, KHÔNG thêm text giải thích bên ngoài.\n"
        f"```json\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n```"
    )


async def extractor_node(state: EvaluationState) -> dict:
    """Node bóc tách CV: text thô → CVInformation (structured).
    
    Sử dụng extraction LLM (temperature thấp) để đảm bảo
    bóc tách chính xác, không hallucinate dữ liệu.
    Dùng method='json_mode' tương thích với LLM server local.
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
        # method="json_mode" tương thích tốt với LLM server local (MLX/Ollama)
        structured_llm = llm.with_structured_output(CVInformation, method="json_mode")
        # Thêm schema vào prompt để LLM biết format trả về
        prompt = EXTRACT_PROMPT.format(cv_context=cv_content) + _get_schema_instruction(CVInformation)
        cv_parsed = await _extract_with_retry(structured_llm, prompt)

        # Validation cơ bản
        if not cv_parsed.work_experience and not cv_parsed.skills and not cv_parsed.education:
            logger.warning("⚠ CV được parse nhưng không có dữ liệu quan trọng")

        logger.info("✔ Xử lý extractor_node thành công")
        return {"cv_parsed": cv_parsed}

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi bóc tách CV: {str(e)}"]}
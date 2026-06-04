from src.core.logger import get_logger
from src.utils import get_extraction_llm
from src.agents.evaluation_agent.output_schema import JDRequirements
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.prompt import PARSE_JD_PROMPT
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(
        f"Retry parse_jd_node lần {retry_state.attempt_number}: {retry_state.outcome.exception()}"
    ),
)
async def _parse_jd_with_retry(structured_llm, prompt: str) -> JDRequirements:
    """Gọi LLM có retry với exponential backoff."""
    return await structured_llm.ainvoke(prompt)


def _get_schema_instruction(schema_class) -> str:
    """Tạo hướng dẫn JSON schema từ Pydantic model."""
    schema = schema_class.model_json_schema()
    return (
        "\n\nHãy trả kết quả dưới dạng JSON hợp lệ theo đúng schema sau. "
        "CHỈ trả JSON, KHÔNG thêm text giải thích bên ngoài.\n"
        f"```json\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n```"
    )


async def parse_jd_node(state: EvaluationState) -> dict:
    """Node phân tích JD: text thô → JDRequirements (structured).
    
    Tách riêng must-have vs nice-to-have skills,
    trích xuất yêu cầu kinh nghiệm và học vấn.
    Dùng method='json_mode' tương thích với LLM server local.
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
        structured_llm = llm.with_structured_output(JDRequirements, method="json_mode")
        prompt = PARSE_JD_PROMPT.format(jd_context=job_requirement) + _get_schema_instruction(JDRequirements)
        jd_parsed = await _parse_jd_with_retry(structured_llm, prompt)

        # Log tóm tắt
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

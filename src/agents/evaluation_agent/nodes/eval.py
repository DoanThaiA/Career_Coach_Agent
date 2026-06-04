from src.core.logger import get_logger
from src.utils import get_evaluation_llm
from src.agents.evaluation_agent.prompt import EVAL_PROMPT
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import EvaluationReport, Recommendation
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json

logger = get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(
        f"Retry eval_node lần {retry_state.attempt_number}: {retry_state.outcome.exception()}"
    ),
)
async def _eval_with_retry(structured_llm, prompt: str) -> EvaluationReport:
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


def validate_report(report: EvaluationReport) -> EvaluationReport:
    """Post-processing: đảm bảo consistency giữa score và recommendation.
    
    Tự động chỉnh recommendation nếu LLM trả sai logic:
    - overall_score >= 70 → PASS
    - 50 <= overall_score < 70 → CONSIDER
    - overall_score < 50 → REJECT
    """
    expected = (
        Recommendation.PASS if report.overall_score >= 70
        else Recommendation.CONSIDER if report.overall_score >= 50
        else Recommendation.REJECT
    )
    if report.recommendation != expected:
        logger.warning(
            f"⚠ Recommendation không khớp score: "
            f"score={report.overall_score}, LLM trả={report.recommendation.value}, "
            f"sửa thành={expected.value}"
        )
        report.recommendation = expected

    return report


async def eval_node(state: EvaluationState) -> dict:
    """Node đánh giá: CVInformation + JDRequirements → EvaluationReport.
    
    Sử dụng evaluation LLM (temperature vừa phải) để cân bằng
    giữa sáng tạo (viết lại CV) và chính xác (chấm điểm).
    Dùng method='json_mode' tương thích với LLM server local.
    """
    logger.info("▶ Bắt đầu xử lý eval_node ...")

    cv_parsed = state.get("cv_parsed")
    jd_parsed = state.get("jd_parsed")

    if not cv_parsed:
        logger.warning("✖ Không tìm thấy CV đã phân tích (cv_parsed)")
        return {"errors": ["Không tìm thấy CV đã phân tích"]}

    if not jd_parsed:
        logger.warning("✖ Không tìm thấy JD đã phân tích (jd_parsed)")
        return {"errors": ["Không tìm thấy JD đã phân tích"]}

    try:
        llm = get_evaluation_llm()
        structured_llm = llm.with_structured_output(EvaluationReport, method="json_mode")

        prompt = EVAL_PROMPT.format(
            cv_data=cv_parsed.model_dump_json(indent=2),
            jd_data=jd_parsed.model_dump_json(indent=2),
        ) + _get_schema_instruction(EvaluationReport)
        eval_report = await _eval_with_retry(structured_llm, prompt)

        # Post-processing validation
        eval_report = validate_report(eval_report)

        # Log tóm tắt
        logger.info(
            f"✔ Đánh giá hoàn tất: Score={eval_report.overall_score}/100, "
            f"Recommendation={eval_report.recommendation.value}, "
            f"Skills matched={sum(1 for s in eval_report.skill_analysis if s.matched)}/"
            f"{len(eval_report.skill_analysis)}"
        )
        return {"eval_report": eval_report}

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý eval_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi đánh giá CV: {str(e)}"]}
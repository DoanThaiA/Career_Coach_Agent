from langchain_core.messages import AIMessage, HumanMessage
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.prompt import SCORING_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import TopicScoreResult
from src.core.logger import get_logger
from langchain_core.runnables.config import RunnableConfig

logger = get_logger(__name__)


def _build_conversation_context(messages: list) -> str:
    """Xây dựng lịch sử hội thoại dưới dạng văn bản có cấu trúc."""
    parts = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            parts.append(f"Interviewer: {msg.content}")
        elif isinstance(msg, HumanMessage):
            parts.append(f"Ứng viên: {msg.content}")
    return "\n".join(parts) if parts else "Không có lịch sử hội thoại."


async def scoring_engine(state: InterviewState, config: RunnableConfig) -> dict:
    """Chấm điểm năng lực ứng viên cho chủ đề hiện tại.

    Sử dụng cả extracted_evidence VÀ lịch sử hội thoại để đánh giá
    chính xác hơn, tránh trường hợp evidence bị thiếu sót.
    """
    logger.info("▶ Bắt đầu scoring_engine_node ...")

    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)

    if current_idx >= len(topics):
        return {"errors": ["Chỉ mục chủ đề không hợp lệ."]}

    current_topic = topics[current_idx]
    topic_key = current_topic.get("topic_name", f"Topic_{current_idx}")

    extracted_evidence = state.get("extracted_evidence", {}).get(topic_key, {})

    # Auto-score 1 nếu hoàn toàn lạc đề và không có bằng chứng
    if extracted_evidence.get("is_off_topic") is True and not extracted_evidence.get("key_points"):
        logger.warning(f"⚠ Ứng viên lạc đề hoàn toàn. Auto-score 1/10 cho '{topic_key}'")
        scores = dict(state.get("topic_scores", {}))
        scores[topic_key] = 1
        reasonings = dict(state.get("score_reasonings", {}))
        reasonings[topic_key] = "Ứng viên lạc đề hoặc không cung cấp bằng chứng liên quan. Hệ thống chấm điểm tối thiểu."
        return {"topic_scores": scores, "score_reasonings": reasonings}

    try:
        llm = get_extraction_llm()

        # Định dạng bằng chứng
        key_points = extracted_evidence.get("key_points", [])
        evidence_text = "\n".join([f"- {p}" for p in key_points]) if key_points else "Không có bằng chứng rõ ràng."

        # Dùng slim JD text đã cache từ interview_plan để tiết kiệm token
        jd = state.get("jd_parsed")
        jd_text = state.get("slim_jd_text") or (jd.model_dump_json(indent=None, ensure_ascii=False) if jd else "Không có JD.")

        # Lấy lịch sử hội thoại của topic hiện tại (từ sau lần hỏi topic trước)
        all_messages = state.get("messages", [])
        conversation_text = _build_conversation_context(all_messages)

        prompt = SCORING_PROMPT.format(
            jd_parsed=jd_text,
            topic_name=topic_key,
            expected_outcome=current_topic.get("expected_outcome", ""),
            extracted_evidence=evidence_text,
            conversation_history=conversation_text,
        ) + get_schema_instruction(TopicScoreResult)

        result = await generate_with_retry_and_correction(llm, prompt, TopicScoreResult, max_retries=3, config=config)

        scores = dict(state.get("topic_scores", {}))
        scores[topic_key] = result.score
        reasonings = dict(state.get("score_reasonings", {}))
        reasonings[topic_key] = result.reasoning

        logger.info(f"✔ Đã chấm điểm '{topic_key}': {result.score}/10")
        return {"topic_scores": scores, "score_reasonings": reasonings}

    except Exception as e:
        logger.error(f"✖ Lỗi scoring_engine topic '{topic_key}': {e}")
        return {"errors": [f"Lỗi chấm điểm: {str(e)}"]}
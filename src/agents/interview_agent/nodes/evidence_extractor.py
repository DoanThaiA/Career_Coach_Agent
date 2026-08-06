from langchain_core.messages import AIMessage, HumanMessage
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import ExtractedEvidence
from src.agents.interview_agent.prompt import EVIDENCE_EXTRACTOR_PROMPT
from src.core.logger import get_logger
from langchain_core.runnables.config import RunnableConfig

logger = get_logger(__name__)


async def evidence_extractor(state: InterviewState, config: RunnableConfig) -> dict:
    """Bóc tách dẫn chứng từ câu trả lời mới nhất của ứng viên.

    Tìm cặp (AIMessage, HumanMessage) cuối cùng trong lịch sử hội thoại
    thay vì dùng index cứng để tránh lỗi khi có nhiều vòng follow-up.
    """
    logger.info("▶ Bắt đầu evidence_extractor_node ...")

    messages = state.get("messages", [])
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)

    if current_idx >= len(topics):
        return {"errors": ["Chỉ mục chủ đề không hợp lệ."]}

    # Tìm cặp (câu hỏi AI, câu trả lời Human) gần nhất bằng cách duyệt ngược
    candidate_answer: str | None = None
    interviewer_question: str | None = None

    for msg in reversed(messages):
        if candidate_answer is None and isinstance(msg, HumanMessage):
            candidate_answer = msg.content
        elif candidate_answer is not None and isinstance(msg, AIMessage):
            interviewer_question = msg.content
            break

    if not candidate_answer or not interviewer_question:
        return {"errors": ["Không tìm thấy cặp câu hỏi/câu trả lời hợp lệ trong lịch sử hội thoại."]}

    current_topic = topics[current_idx]
    topic_key = current_topic.get("topic_name", f"Topic_{current_idx}")

    try:
        llm = get_extraction_llm()
        prompt = EVIDENCE_EXTRACTOR_PROMPT.format(
            topic_name=topic_key,
            interviewer_question=interviewer_question,
            candidate_answer=candidate_answer,
        ) + get_schema_instruction(ExtractedEvidence)

        result = await generate_with_retry_and_correction(
            llm, prompt, ExtractedEvidence, max_retries=3, config=config
        )

        current_evidence = dict(state.get("extracted_evidence", {}))
        existing = current_evidence.get(topic_key, {})

        # Gộp key_points qua nhiều vòng hỏi thay vì ghi đè
        merged_points = list(existing.get("key_points", [])) + result.key_points
        current_evidence[topic_key] = {
            "key_points": merged_points,
            "is_off_topic": result.is_off_topic and not merged_points,
        }

        logger.info(f"✔ Đã bóc tách {len(result.key_points)} điểm mới cho '{topic_key}' (tổng: {len(merged_points)})")
        return {"extracted_evidence": current_evidence}

    except Exception as e:
        logger.error(f"✖ Lỗi evidence_extractor: {e}")
        return {"errors": [f"Lỗi bóc tách câu trả lời: {str(e)}"]}

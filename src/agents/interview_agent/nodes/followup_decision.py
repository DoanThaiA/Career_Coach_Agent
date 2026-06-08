from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

MAX_FOLLOWUP_PER_TOPIC = 2

async def followup_decision(state: InterviewState) -> dict:
    """Node quyết định có cần hỏi follow-up hay không.
    
    Logic:
    - Nếu điểm < 7 VÀ chưa follow-up đủ MAX_FOLLOWUP_PER_TOPIC lần → hỏi thêm
    - Ngược lại → chốt chủ đề, chuyển sang topic tiếp theo
    """
    logger.info("▶ Bắt đầu xử lý followup_decision_node ...")
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)
    
    if current_idx >= len(topics):
        logger.warning("⚠ current_topic_index vượt quá danh sách topics.")
        return {"requires_followup": False}
    
    current_topic = topics[current_idx]
    topic_key = current_topic.get("topic_name", f"Topic_{current_idx}")
    
    scores = state.get("topic_scores", {})
    current_score = scores.get(topic_key, 0)

    current_followup_count = state.get("followup_count", 0)
    
    need_followup = current_score < 7 and current_followup_count < MAX_FOLLOWUP_PER_TOPIC

    if need_followup:
        logger.info(
            f"➡ Topic '{topic_key}' điểm {current_score}/10, "
            f"follow-up lần {current_followup_count + 1}/{MAX_FOLLOWUP_PER_TOPIC}"
        )
    else:
        reason = (
            f"đủ điểm ({current_score})" 
            if current_score >= 7 
            else f"đã follow-up đủ ({current_followup_count}/{MAX_FOLLOWUP_PER_TOPIC})"
        )
        logger.info(f"✔ Topic '{topic_key}' chốt — {reason}")

    return {
        "requires_followup": need_followup,
        "followup_count": current_followup_count + 1 if need_followup else current_followup_count
    }
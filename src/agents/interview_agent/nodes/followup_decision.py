from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

# Hỏi follow-up khi điểm dưới ngưỡng này
FOLLOWUP_SCORE_THRESHOLD = 6
# Số lần follow-up tối đa cho mỗi topic (hard cap per-topic, tránh loop vô tận)
MAX_FOLLOWUP_PER_TOPIC = 2


async def followup_decision(state: InterviewState) -> dict:
    """Quyết định có cần hỏi follow-up hay không.

    Logic:
    - Hỏi thêm nếu: điểm < FOLLOWUP_SCORE_THRESHOLD VÀ chưa đạt giới hạn follow-up PER TOPIC.
    - Chốt topic nếu: điểm đủ cao HOẶC đã hỏi đủ số lần tối đa cho topic này.
    
    Dùng followup_count_per_topic (per-topic counter) thay vì followup_count (global counter)
    để mỗi topic độc lập, không bị ảnh hưởng bởi topic trước.
    """
    logger.info("▶ Bắt đầu followup_decision_node ...")

    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)

    if current_idx >= len(topics):
        return {"requires_followup": False}

    topic_key = topics[current_idx].get("topic_name", f"Topic_{current_idx}")
    current_score = state.get("topic_scores", {}).get(topic_key, 0)

    # Per-topic counter: mỗi topic có giới hạn riêng
    per_topic_counts = dict(state.get("followup_count_per_topic", {}))
    topic_followup_count = per_topic_counts.get(topic_key, 0)

    need_followup = (
        current_score < FOLLOWUP_SCORE_THRESHOLD
        and topic_followup_count < MAX_FOLLOWUP_PER_TOPIC
    )

    if need_followup:
        per_topic_counts[topic_key] = topic_followup_count + 1
        logger.info(
            f"↩ Topic '{topic_key}': điểm {current_score}/10 < {FOLLOWUP_SCORE_THRESHOLD}, "
            f"hỏi follow-up lần {topic_followup_count + 1}/{MAX_FOLLOWUP_PER_TOPIC}"
        )
    else:
        reason = (
            f"điểm đủ ({current_score}/{FOLLOWUP_SCORE_THRESHOLD})"
            if current_score >= FOLLOWUP_SCORE_THRESHOLD
            else f"đã follow-up đủ {topic_followup_count}/{MAX_FOLLOWUP_PER_TOPIC} lần cho topic này"
        )
        logger.info(f"✔ Topic '{topic_key}' chốt — {reason}")

    return {
        "requires_followup": need_followup,
        "followup_count_per_topic": per_topic_counts,
        # Giữ followup_count global để tương thích
        "followup_count": state.get("followup_count", 0) + (1 if need_followup else 0),
    }
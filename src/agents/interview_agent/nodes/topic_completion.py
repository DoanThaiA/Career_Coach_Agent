from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)


async def topic_completion(state: InterviewState) -> dict:
    """Chuyển sang chủ đề tiếp theo sau khi hoàn tất khai thác."""
    current_idx = state.get("current_topic_index", 0)
    topics = state.get("topics", [])

    topic_name = topics[current_idx].get("topic_name", "Unknown") if current_idx < len(topics) else "Unknown"
    logger.info(f"✔ Đã hoàn tất chủ đề '{topic_name}'. Chuyển sang topic {current_idx + 1}.")

    return {
        "current_topic_index": current_idx + 1,
        "followup_count": 0,
        "requires_followup": False,
    }
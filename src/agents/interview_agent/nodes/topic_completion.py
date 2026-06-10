from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

async def topic_completion(state: InterviewState) -> dict:
    """Node xử lý logic khi một chủ đề đã hoàn tất."""
    logger.info(" Bắt đầu xử lý topic_completion_node ...")
    
    current_idx = state.get("current_topic_index", 0)
    topics = state.get("topics", [])
    
    topic_name = topics[current_idx].get("topic_name") if current_idx < len(topics) else "Unknown"
    logger.info(f"✔ Đã hoàn tất khai thác chủ đề: '{topic_name}'")
    
    next_idx = current_idx + 1
    
    return {
        "current_topic_index": next_idx,
        "followup_count": 0,
        "requires_followup": False
    }
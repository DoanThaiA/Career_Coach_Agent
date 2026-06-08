from langchain_core.messages import AIMessage
from src.utils import get_llm
from src.agents.interview_agent.prompt import FOLLOWUP_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

async def followup_generator(state: InterviewState) -> dict:
    """Node sinh câu hỏi follow-up để khai thác sâu hơn chủ đề hiện tại."""
    logger.info("▶ Bắt đầu xử lý followup_generator_node ...")
    
    messages = state.get("messages", [])
    last_answer = messages[-1].content if messages else ""
    
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)
    
    if current_idx >= len(topics):
        logger.warning("⚠ current_topic_index vượt quá danh sách topics.")
        return {"errors": ["Không tìm thấy topic hiện tại để sinh follow-up."]}
    
    topic_key = topics[current_idx].get("topic_name", "")
    
    # Lấy lý do thiếu sót từ ScoringEngine
    reasonings = state.get("score_reasonings", {})
    topic_reasoning = reasonings.get(topic_key, "Chưa rõ chi tiết thực hành.")
    
    try:
        llm = get_llm()
        prompt = FOLLOWUP_PROMPT.format(
            topic_name=topic_key,
            last_answer=last_answer,
            reasoning=topic_reasoning
        )
        
        response = await llm.ainvoke(prompt)
        
        logger.info(f"✔ Đã sinh câu hỏi follow-up cho topic: '{topic_key}'")
        return {"messages": [AIMessage(content=response.content)]}
        
    except Exception as e:
        logger.error(f"✖ Lỗi khi sinh câu hỏi follow-up: {e}")
        return {"errors": [f"Lỗi sinh follow-up: {str(e)}"]}
from langchain_core.messages import AIMessage, HumanMessage
from src.utils import get_llm
from src.agents.interview_agent.prompt import FOLLOWUP_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger
from langchain_core.runnables.config import RunnableConfig

logger = get_logger(__name__)


async def followup_generator(state: InterviewState, config: RunnableConfig) -> dict:
    """Sinh câu hỏi follow-up để khai thác sâu hơn chủ đề hiện tại."""
    logger.info("▶ Bắt đầu followup_generator_node ...")

    messages = state.get("messages", [])
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)

    if current_idx >= len(topics):
        return {"errors": ["Không tìm thấy topic hiện tại để sinh follow-up."]}

    topic_key = topics[current_idx].get("topic_name", "")

    # Lấy câu trả lời gần nhất của ứng viên
    last_answer = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_answer = msg.content
            break

    # Lấy lý do chưa đạt điểm từ scoring engine
    reasonings = state.get("score_reasonings", {})
    topic_reasoning = reasonings.get(topic_key, "Chưa rõ chi tiết thực hành.")

    try:
        llm = get_llm()
        prompt = FOLLOWUP_PROMPT.format(
            topic_name=topic_key,
            last_answer=last_answer,
            reasoning=topic_reasoning,
        )
        response = await llm.ainvoke(prompt, config=config)

        logger.info(f"✔ Đã sinh câu hỏi follow-up cho topic: '{topic_key}'")
        return {"messages": [AIMessage(content=response.content)]}

    except Exception as e:
        logger.error(f"✖ Lỗi followup_generator: {e}")
        return {"errors": [f"Lỗi sinh follow-up: {str(e)}"]}
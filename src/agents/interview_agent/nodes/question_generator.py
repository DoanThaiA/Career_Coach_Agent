from langchain_core.messages import AIMessage
from src.utils import get_llm
from src.agents.interview_agent.prompt import QUESTION_GENERATOR_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

async def question_generator(state: InterviewState) -> dict:
    """Node sinh câu hỏi phỏng vấn cho chủ đề hiện tại."""
    logger.info("▶ Bắt đầu xử lý question_generator_node ...")
    topics = state.get("topics", [])
    current_topic_index = state.get("current_topic_index", 0)

    if current_topic_index >= len(topics):
        logger.warning("⚠ Đã xử lý hết tất cả các topics.")
        return {"errors": ["Đã xử lý hết tất cả các topics"]}
    
    topic = topics[current_topic_index]
    try:
        llm = get_llm()
        prompt = QUESTION_GENERATOR_PROMPT.format(
            topic_name=topic['topic_name'],
            context_source=topic['context_source'],
            expected_outcome=topic['expected_outcome']
        )
        response = await llm.ainvoke(prompt)
        ai_msg = AIMessage(content=response.content)
        
        logger.info(f"✔ Đã sinh câu hỏi cho topic: '{topic['topic_name']}'")
        return {
            "messages": [ai_msg]
        }    
    except Exception as e:
        logger.error(f"✖ Lỗi khi sinh câu hỏi: {e}")
        return {"errors": [f"Lỗi sinh câu hỏi: {str(e)}"]}

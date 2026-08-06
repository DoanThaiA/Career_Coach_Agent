from langchain_core.messages import AIMessage
from src.utils import get_llm
from src.agents.interview_agent.prompt import QUESTION_GENERATOR_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger
from langchain_core.runnables.config import RunnableConfig

logger = get_logger(__name__)


async def question_generator(state: InterviewState, config: RunnableConfig) -> dict:
    """Sinh câu hỏi phỏng vấn cho chủ đề hiện tại.

    Truyền thêm jd_context (job_title, level) vào prompt để sinh câu hỏi
    đúng độ khó và phù hợp với vị trí tuyển dụng.
    """
    logger.info("▶ Bắt đầu question_generator_node ...")

    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)

    if current_idx >= len(topics):
        return {"errors": ["Đã xử lý hết tất cả các topics."]}

    topic = topics[current_idx]
    jd = state.get("jd_parsed")

    # Xây dựng ngữ cảnh JD để hỗ trợ sinh câu hỏi đúng cấp độ
    job_title = jd.job_title if jd else "Unknown"
    level = jd.level if jd and jd.level else "Mid-level"

    try:
        llm = get_llm()
        prompt = QUESTION_GENERATOR_PROMPT.format(
            topic_name=topic["topic_name"],
            context_source=topic["context_source"],
            expected_outcome=topic["expected_outcome"],
            job_title=job_title,
            level=level,
        )
        response = await llm.ainvoke(prompt, config=config)

        logger.info(f"✔ Đã sinh câu hỏi cho topic {current_idx + 1}/{len(topics)}: '{topic['topic_name']}'")
        return {"messages": [AIMessage(content=response.content)]}

    except Exception as e:
        logger.error(f"✖ Lỗi question_generator: {e}")
        return {"errors": [f"Lỗi sinh câu hỏi: {str(e)}"]}

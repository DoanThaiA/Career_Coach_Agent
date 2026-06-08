from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import ExtractedEvidence
from src.agents.interview_agent.prompt import EVIDENCE_EXTRACTOR_PROMPT
from src.core.logger import get_logger

logger = get_logger(__name__)


async def evidence_extractor(state: InterviewState) -> dict:
    """Node bóc tách dẫn chứng từ câu trả lời của ứng viên."""
    logger.info("▶ Bắt đầu xử lý evidence_extractor_node ...")
    
    messages = state.get("messages", [])
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)
    
    if len(messages) < 2:
        return {"errors": ["Không đủ lịch sử hội thoại để bóc tách."]}

    if current_idx >= len(topics):
        logger.warning("⚠ current_topic_index vượt quá danh sách topics.")
        return {"errors": ["Chỉ mục chủ đề hiện tại không hợp lệ."]}

    # Lấy câu hỏi gần nhất (AIMessage) và câu trả lời gần nhất (HumanMessage)
    candidate_answer = messages[-1].content
    interviewer_question = messages[-2].content
    current_topic = topics[current_idx]
    
    try:
        llm = get_extraction_llm()
        
        prompt = EVIDENCE_EXTRACTOR_PROMPT.format(
            topic_name=current_topic.get("topic_name", ""),
            interviewer_question=interviewer_question,
            candidate_answer=candidate_answer
        ) + get_schema_instruction(ExtractedEvidence)
        
        result = await generate_with_retry_and_correction(
            llm, prompt, ExtractedEvidence, max_retries=3
        )
        
        # Tạo bản copy mới thay vì mutate state trực tiếp
        current_evidence_dict = dict(state.get("extracted_evidence", {}))
        topic_key = current_topic.get("topic_name", f"Topic_{current_idx}")
        
        current_evidence_dict[topic_key] = result.model_dump()
        
        logger.info(f"✔ Đã bóc tách dẫn chứng cho topic: '{topic_key}'")
        
        return {"extracted_evidence": current_evidence_dict}
        
    except Exception as e:
        logger.error(f"✖ Lỗi khi bóc tách dẫn chứng: {e}")
        return {"errors": [f"Lỗi khi bóc tách câu trả lời: {str(e)}"]}

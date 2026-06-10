from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.prompt import SCORING_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import TopicScoreResult
from src.core.logger import get_logger

logger = get_logger(__name__)

async def scoring_engine(state: InterviewState) -> dict:
    """Node chấm điểm topic dựa trên bằng chứng trích xuất."""
    logger.info("▶ Bắt đầu xử lý scoring_engine_node ...")

    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)
    
    if current_idx >= len(topics):
        logger.warning("⚠ current_topic_index vượt quá danh sách topics.")
        return {"errors": ["Chỉ mục chủ đề hiện tại không hợp lệ."]}
    
    current_topic = topics[current_idx]
    topic_key = current_topic.get("topic_name", f"Topic_{current_idx}")

    extracted_evidence = state.get("extracted_evidence", {}).get(topic_key, {})

    # Trường hợp lạc đề hoặc không có bằng chứng → auto-score 1/10
    if not extracted_evidence or extracted_evidence.get("is_off_topic") is True or not extracted_evidence.get("key_points"):
        logger.warning(f"⚠ Ứng viên lạc đề hoặc không có bằng chứng. Auto-score: 1/10 cho '{topic_key}'")
        current_scores = dict(state.get("topic_scores", {}))
        current_scores[topic_key] = 1
        
        score_reasonings = dict(state.get("score_reasonings", {}))
        score_reasonings[topic_key] = (
            "Ứng viên lạc đề hoặc không cung cấp bằng chứng liên quan đến chủ đề. "
            "Hệ thống tự động chấm điểm tối thiểu."
        )
        return {
            "topic_scores": current_scores,
            "score_reasonings": score_reasonings
        }
    
    try:
        llm = get_extraction_llm()
        evidence_text = "\n".join([f"- {point}" for point in extracted_evidence.get("key_points", [])])
        
        # Serialize jd_parsed thành JSON readable thay vì raw object
        jd_parsed = state.get("jd_parsed")
        jd_text = jd_parsed.model_dump_json(indent=2, ensure_ascii=False) if jd_parsed else "Không có JD"
        
        prompt = SCORING_PROMPT.format(
            jd_parsed=jd_text,
            topic_name=topic_key,
            expected_outcome=current_topic.get("expected_outcome", "Không có thông tin kỳ vọng."),
            extracted_evidence=evidence_text
        ) + get_schema_instruction(TopicScoreResult)

        result = await generate_with_retry_and_correction(
            llm, prompt, TopicScoreResult, max_retries=3
        )
        
        # Tạo bản copy mới thay vì mutate state trực tiếp
        current_scores = dict(state.get("topic_scores", {}))
        current_scores[topic_key] = result.score
        
        score_reasonings = dict(state.get("score_reasonings", {}))
        score_reasonings[topic_key] = result.reasoning
        
        logger.info(f"✔ Đã chấm điểm '{topic_key}': {result.score}/10")
        return {
            "topic_scores": current_scores,
            "score_reasonings": score_reasonings
        }
    except Exception as e:
        logger.error(f"✖ Lỗi khi chấm điểm chủ đề {topic_key}: {e}")
        return {"errors": [f"Lỗi khi chấm điểm: {str(e)}"]}
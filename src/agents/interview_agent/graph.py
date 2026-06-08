from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

from src.agents.interview_agent.nodes import (
    interview_plan,
    early_rejection,
    question_generator,
    evidence_extractor,
    scoring_engine,
    followup_decision,
    followup_generator,
    topic_completion,
    report_generator
)

logger = get_logger(__name__)


def route_after_planner(state: InterviewState) -> str:
    """Kiểm tra xem quá trình lập kịch bản có lỗi không."""
    errors = state.get("errors", [])
    if errors and len(errors) > 0:
        logger.warning("Luồng rẽ vào early_rejection_node do có lỗi.")
        return "early_rejection_node"
    return "question_generator_node"

def route_after_decision(state: InterviewState) -> str:
    """Quyết định hỏi xoáy hay chốt chủ đề dựa trên cờ requires_followup."""
    if state.get("requires_followup") is True:
        logger.info("Luồng rẽ vào followup_generator_node (Hỏi xoáy).")
        return "followup_generator_node"
    
    logger.info("Luồng rẽ vào topic_completion_node (Chốt chủ đề).")
    return "topic_completion_node"

def route_topic_completion(state: InterviewState) -> str:
    """Kiểm tra tiến độ danh sách chủ đề."""
    current_idx = state.get("current_topic_index", 0)
    topics = state.get("topics", [])
    
    if current_idx < len(topics):
        logger.info("Luồng quay lại question_generator_node (Chủ đề mới).")
        return "question_generator_node"
    
    logger.info("Đã hết chủ đề. Luồng rẽ vào report_generator_node.")
    return "report_generator_node"




def build_interview_graph():
    """Hàm khởi tạo và biên dịch Graph."""
    
    workflow = StateGraph(InterviewState)
    
    # Thêm tất cả các Node vào Graph
    workflow.add_node("interview_plan_node", interview_plan)
    workflow.add_node("early_rejection_node", early_rejection)
    workflow.add_node("question_generator_node", question_generator)
    workflow.add_node("evidence_extractor_node", evidence_extractor)
    workflow.add_node("scoring_engine_node", scoring_engine)
    workflow.add_node("followup_decision_node", followup_decision)
    workflow.add_node("followup_generator_node", followup_generator)
    workflow.add_node("topic_completion_node", topic_completion)
    workflow.add_node("report_generator_node", report_generator)
    

    # Điểm bắt đầu
    workflow.set_entry_point("interview_plan_node")
    
    # Rẽ nhánh 1: Sau khi lập kế hoạch
    workflow.add_conditional_edges(
        "interview_plan_node",
        route_after_planner,
        {
            "early_rejection_node": "early_rejection_node",
            "question_generator_node": "question_generator_node"
        }
    )
    workflow.add_edge("early_rejection_node", END)
    
    # Tuyến tính: Sau khi sinh câu hỏi -> bóc tách -> chấm điểm -> ra quyết định
    workflow.add_edge("question_generator_node", "evidence_extractor_node")
    workflow.add_edge("evidence_extractor_node", "scoring_engine_node")
    workflow.add_edge("scoring_engine_node", "followup_decision_node")
    
    # Rẽ nhánh 2: Quyết định có hỏi phụ không
    workflow.add_conditional_edges(
        "followup_decision_node",
        route_after_decision,
        {
            "followup_generator_node": "followup_generator_node",
            "topic_completion_node": "topic_completion_node"
        }
    )
    
    # Nếu sinh câu hỏi phụ xong -> Lại quay về bóc tách (Vòng lặp nhỏ)
    workflow.add_edge("followup_generator_node", "evidence_extractor_node")
    
    # Rẽ nhánh 3: Hoàn tất một chủ đề
    workflow.add_conditional_edges(
        "topic_completion_node",
        route_topic_completion,
        {
            "question_generator_node": "question_generator_node",
            "report_generator_node": "report_generator_node"
        }
    )
    
    # Điểm kết thúc: Sinh báo cáo xong là nghỉ
    workflow.add_edge("report_generator_node", END)
    
    memory = MemorySaver()
    
    # BIÊN DỊCH GRAPH
    interview_agent = workflow.compile(
        checkpointer=memory,

        interrupt_after=[
            "question_generator_node", 
            "followup_generator_node"
        ]
    )
    
    return interview_agent

# Khởi tạo instance dùng chung
interview_app = build_interview_graph()
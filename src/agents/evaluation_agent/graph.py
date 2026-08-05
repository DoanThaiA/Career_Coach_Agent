
from langgraph.graph import StateGraph, START, END
from src.agents.evaluation_agent.state import EvaluationState

from src.agents.evaluation_agent.nodes.eval_skills import eval_skills_node
from src.agents.evaluation_agent.nodes.eval_experience import eval_experience_node
from src.agents.evaluation_agent.nodes.eval_final import eval_final_node
from src.core.logger import get_logger

logger = get_logger(__name__)

def validate_input(state: EvaluationState) -> str:
    """Kiểm tra xem đầu vào đã có sẵn cv_parsed và jd_parsed chưa.
    
    Chỉ cho phép evaluate nếu:
    - Không có errors
    - cv_parsed đã có
    - jd_parsed đã có
    """
    if state.get("errors"):
        logger.warning(f"✖ Phát hiện lỗi, dừng pipeline: {state['errors']}")
        return "end"
    if not state.get("cv_parsed"):
        logger.warning("✖ Thiếu cv_parsed (schema CV), dừng pipeline")
        return "end"
    if not state.get("jd_parsed"):
        logger.warning("✖ Thiếu jd_parsed (schema JD), dừng pipeline")
        return "end"
    return "start_evaluate"


def start_evaluate(state: EvaluationState) -> dict:
    """Fan-out node: khởi động eval_skills và eval_experience song song."""
    return {}




def check_eval_readiness(state: EvaluationState) -> dict:
    """Fan-in node: chờ eval_skills và eval_experience hoàn thành."""
    return {}

def should_finalize(state: EvaluationState) -> str:
    if state.get("errors"):
        logger.warning(f"✖ Phát hiện lỗi trong lúc evaluate, dừng: {state['errors']}")
        return "end"
    if not state.get("skill_evaluation") or not state.get("experience_evaluation"):
        logger.warning("✖ Thiếu kết quả đánh giá trung gian, dừng pipeline")
        return "end"
    return "finalize"


# ──────────────────────────────────────────────
# Graph construction
# ──────────────────────────────────────────────

def build_evaluation_graph():
    """Xây dựng và compile evaluation graph.
    
    Pattern: Fan-out / Fan-in
    - START → validate_input (kiểm tra schema)
    - Nếu có schema → start_evaluate (fan-out → eval_skills + eval_experience)
    - Nếu thiếu schema → END
    
    Returns:
        CompiledStateGraph: Graph đã compile, sẵn sàng invoke.
        
    Usage:
        graph = build_evaluation_graph()
        result = await graph.ainvoke({
            "cv_parsed": ...,  # Schema CVInformation
            "jd_parsed": ...,  # Schema JDRequirements
            "errors": [],
        })
    """
    graph = StateGraph(EvaluationState)

    # Thêm nodes

    
    # Các nodes đánh giá trung gian
    graph.add_node("start_evaluate", start_evaluate)
    graph.add_node("eval_skills", eval_skills_node)
    graph.add_node("eval_experience", eval_experience_node)
    graph.add_node("check_eval_readiness", check_eval_readiness)
    
    # Node tổng hợp
    graph.add_node("eval_final", eval_final_node)

    # Kiểm tra input → bắt đầu evaluate hoặc END
    graph.add_conditional_edges(
        START,
        validate_input,
        {
            "start_evaluate": "start_evaluate",
            "end": END,
        },
    )

    # Fan-out 2: start_evaluate → 2 node evaluation chạy song song
    graph.add_edge("start_evaluate", "eval_skills")
    graph.add_edge("start_evaluate", "eval_experience")

    # Fan-in 2: cả 2 node evaluation → check_eval_readiness
    graph.add_edge("eval_skills", "check_eval_readiness")
    graph.add_edge("eval_experience", "check_eval_readiness")
    
    # Kiểm tra → tổng hợp final hoặc END
    graph.add_conditional_edges(
        "check_eval_readiness",
        should_finalize,
        {
            "finalize": "eval_final",
            "end": END,
        },
    )

    # eval_final → END
    graph.add_edge("eval_final", END)

    compiled = graph.compile()
    logger.info("✔ Evaluation graph compiled thành công")
    return compiled


# Singleton compiled graph
_compiled_graph = None


def get_evaluation_graph():
    """Lấy compiled graph (singleton pattern).
    
    Returns:
        CompiledStateGraph: Graph đã compile.
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_evaluation_graph()
    return _compiled_graph

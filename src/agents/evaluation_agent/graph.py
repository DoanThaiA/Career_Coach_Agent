
from langgraph.graph import StateGraph, START, END
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.nodes.extract_cv import extractor_node
from src.agents.evaluation_agent.nodes.parse_jd import parse_jd_node
from src.agents.evaluation_agent.nodes.eval_skills import eval_skills_node
from src.agents.evaluation_agent.nodes.eval_experience import eval_experience_node
from src.agents.evaluation_agent.nodes.eval_final import eval_final_node
from src.core.logger import get_logger

logger = get_logger(__name__)

def check_readiness(state: EvaluationState) -> dict:
    """Fan-in node: chờ cả extract_cv và parse_jd hoàn thành."""
    return {}


def start_evaluate(state: EvaluationState) -> dict:
    """Fan-out node: khởi động eval_skills và eval_experience song song."""
    return {}


def should_evaluate(state: EvaluationState) -> str:
    """Kiểm tra sau khi cả 2 node parsing hoàn thành.
    
    Chỉ cho phép evaluate nếu:
    - Không có errors
    - cv_parsed đã có
    - jd_parsed đã có
    """
    if state.get("errors"):
        logger.warning(f"✖ Phát hiện lỗi, dừng pipeline: {state['errors']}")
        return "end"
    if not state.get("cv_parsed"):
        logger.warning("✖ Thiếu cv_parsed, dừng pipeline")
        return "end"
    if not state.get("jd_parsed"):
        logger.warning("✖ Thiếu jd_parsed, dừng pipeline")
        return "end"
    return "evaluate"

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
    - START fan-out → extract_cv + parse_jd (chạy song song)
    - check_readiness fan-in ← cả 2 (chờ hoàn thành)
    - evaluate chỉ chạy nếu cả 2 thành công
    
    Returns:
        CompiledStateGraph: Graph đã compile, sẵn sàng invoke.
        
    Usage:
        graph = build_evaluation_graph()
        result = await graph.ainvoke({
            "cv_content": "...",
            "job_requirement": "...",
            "errors": [],
        })
    """
    graph = StateGraph(EvaluationState)

    # Thêm nodes
    graph.add_node("extract_cv", extractor_node)
    graph.add_node("parse_jd", parse_jd_node)
    graph.add_node("check_readiness", check_readiness)
    
    # Các nodes đánh giá trung gian
    graph.add_node("start_evaluate", start_evaluate)
    graph.add_node("eval_skills", eval_skills_node)
    graph.add_node("eval_experience", eval_experience_node)
    graph.add_node("check_eval_readiness", check_eval_readiness)
    
    # Node tổng hợp
    graph.add_node("eval_final", eval_final_node)

    # Fan-out 1: START → cả 2 node parsing chạy song song
    graph.add_edge(START, "extract_cv")
    graph.add_edge(START, "parse_jd")

    # Fan-in 1: cả 2 node parsing → check_readiness
    graph.add_edge("extract_cv", "check_readiness")
    graph.add_edge("parse_jd", "check_readiness")

    # Kiểm tra → bắt đầu evaluate hoặc END
    graph.add_conditional_edges(
        "check_readiness",
        should_evaluate,
        {
            "evaluate": "start_evaluate",
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

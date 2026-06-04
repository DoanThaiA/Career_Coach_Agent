
from langgraph.graph import StateGraph, START, END
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.nodes.extract_cv import extractor_node
from src.agents.evaluation_agent.nodes.parse_jd import parse_jd_node
from src.agents.evaluation_agent.nodes.eval import eval_node
from src.core.logger import get_logger

logger = get_logger(__name__)

def check_readiness(state: EvaluationState) -> dict:
    """Fan-in node: chờ cả extract_cv và parse_jd hoàn thành.
    
    Node này không thay đổi state, chỉ là điểm hội tụ
    để LangGraph đồng bộ 2 nhánh song song.
    """
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
    graph.add_node("evaluate", eval_node)

    # Fan-out: START → cả 2 node chạy song song
    graph.add_edge(START, "extract_cv")
    graph.add_edge(START, "parse_jd")

    # Fan-in: cả 2 node → check_readiness (LangGraph chờ cả 2 xong)
    graph.add_edge("extract_cv", "check_readiness")
    graph.add_edge("parse_jd", "check_readiness")

    # Kiểm tra → evaluate hoặc END
    graph.add_conditional_edges(
        "check_readiness",
        should_evaluate,
        {
            "evaluate": "evaluate",
            "end": END,
        },
    )

    # evaluate → END
    graph.add_edge("evaluate", END)

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

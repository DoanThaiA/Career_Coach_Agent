import asyncio
from typing import Literal
from langgraph.graph import StateGraph, START, END

from src.agents.evaluation_agent.state import EvaluationState
from src.core.logger import get_logger

from src.agents.evaluation_agent.nodes.validate import validate_input, extraction_failed_node
from src.agents.evaluation_agent.nodes.score_skills import score_skills_node
from src.agents.evaluation_agent.nodes.score_experience import score_experience_node
from src.agents.evaluation_agent.nodes.score_education import score_education_node
from src.agents.evaluation_agent.nodes.generate_feedback import generate_feedback_node
from src.agents.evaluation_agent.nodes.aggregate import aggregate_score_node, build_output_node

logger = get_logger(__name__)


async def parallel_score_node(state: EvaluationState, config) -> dict:
    """Chạy song song cả 3 node chấm điểm (skills, experience, education).
    
    Thay vì dùng LangGraph fan-out (thực ra chạy tuần tự), ta dùng asyncio.gather()
    để thực sự parallel hóa 3 tác vụ thuần Python này → giảm latency ~2x.
    """
    # score_skills và score_experience, score_education đều là sync functions
    # Wrap bằng asyncio để chạy song song
    loop = asyncio.get_event_loop()

    skills_result, exp_result, edu_result = await asyncio.gather(
        loop.run_in_executor(None, score_skills_node, state),
        loop.run_in_executor(None, score_experience_node, state),
        loop.run_in_executor(None, score_education_node, state),
    )

    # Merge tất cả kết quả
    merged = {}
    merged.update(skills_result)
    merged.update(exp_result)
    merged.update(edu_result)
    return merged


def route_after_check(state: EvaluationState):
    if state.get("errors"):
        return "extraction_failed"
    return "parallel_score"


def build_evaluation_graph():
    graph = StateGraph(EvaluationState)

    graph.add_node("check_extraction", validate_input)
    graph.add_node("extraction_failed", extraction_failed_node)
    graph.add_node("parallel_score", parallel_score_node)
    graph.add_node("generate_feedback", generate_feedback_node)
    graph.add_node("aggregate_score", aggregate_score_node)
    graph.add_node("build_output", build_output_node)

    graph.add_edge(START, "check_extraction")

    graph.add_conditional_edges(
        "check_extraction",
        route_after_check,
        {"extraction_failed": "extraction_failed", "parallel_score": "parallel_score"}
    )
    graph.add_edge("extraction_failed", END)

    # Sau parallel_score → feedback LLM → aggregate → output
    graph.add_edge("parallel_score", "generate_feedback")
    graph.add_edge("generate_feedback", "aggregate_score")
    graph.add_edge("aggregate_score", "build_output")
    graph.add_edge("build_output", END)

    compiled = graph.compile()
    logger.info("✔ Evaluation graph (Parallel Score + Feedback) compiled thành công")
    return compiled


_compiled_graph = None

def get_evaluation_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_evaluation_graph()
    return _compiled_graph

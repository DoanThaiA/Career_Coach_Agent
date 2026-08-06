import pytest
from src.agents.evaluation_agent.graph import build_evaluation_graph
from src.agents.evaluation_agent.state import EvaluationState

def test_evaluation_graph_compiles():
    """Đảm bảo graph có thể compile thành công mà không có lỗi."""
    graph = build_evaluation_graph()
    assert graph is not None
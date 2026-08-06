from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    val: str

def route(state):
    return "ok"

graph = StateGraph(State)
graph.add_node("A", lambda state: {"val": "A"})
graph.add_node("B", lambda state: {"val": "B"})
graph.add_node("C", lambda state: {"val": "C"})

graph.add_edge(START, "A")

try:
    graph.add_conditional_edges("A", route, {"ok": ["B", "C"]})
    print("Map to list supported!")
except Exception as e:
    print("Map to list failed:", e)

try:
    def route2(state):
        return ["B", "C"]
    
    graph2 = StateGraph(State)
    graph2.add_node("A", lambda state: {"val": "A"})
    graph2.add_node("B", lambda state: {"val": "B"})
    graph2.add_node("C", lambda state: {"val": "C"})
    graph2.add_edge(START, "A")
    graph2.add_conditional_edges("A", route2)
    print("Return list supported!")
except Exception as e:
    print("Return list failed:", e)

from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langchain_core.messages import BaseMessage
import operator
from src.agents.interview_agent.output_schema import CVInformation, JDRequirements

class InterviewState(TypedDict):
    cv_parsed: Optional[CVInformation]
    jd_parsed: Optional[JDRequirements]
    topics: List[Dict]
    current_topic_index:int
    messages: Annotated[List[BaseMessage], operator.add]

    extracted_evidence: Dict[str, List[str]]
    topic_scores: Dict[str, float]
    score_reasonings: Dict[str,str]
    final_decision:str
    report:str

    requires_followup: bool
    followup_count:int
    errors:List[str]

from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langchain_core.messages import BaseMessage
import operator
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements

class InterviewState(TypedDict):
    cv_parsed: Optional[CVInformation]
    jd_parsed: Optional[JDRequirements]
    topics: List[Dict]
    current_topic_index: int
    messages: Annotated[List[BaseMessage], operator.add]

    extracted_evidence: Dict[str, Any]
    topic_scores: Dict[str, float]
    score_reasonings: Dict[str, str]
    final_decision: str
    report: str

    requires_followup: bool
    followup_count: int
    followup_count_per_topic: Dict[str, int]  # Track per-topic followup count
    errors: List[str]

    # Cache slim representations để tránh serialize lại mỗi turn
    slim_cv_text: Optional[str]
    slim_jd_text: Optional[str]

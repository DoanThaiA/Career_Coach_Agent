import uuid
import json
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from src.agents.interview_agent.graph import build_interview_graph
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/interview", tags=["Interview Agent"])

# ── Singleton graph instance ──
_interview_graph = None


def _get_graph():
    """Lazy singleton — build graph 1 lần duy nhất."""
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = build_interview_graph()
        logger.info("✔ Interview graph compiled thành công")
    return _interview_graph


# ══════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════

from pydantic import BaseModel, Field
from typing import Any, Dict, List

from src.api.schemas import InterviewStartByIdRequest


class InterviewStartRequest(BaseModel):
    """Request body để bắt đầu phiên phỏng vấn mới."""
    cv_parsed: Dict[str, Any] = Field(
        ..., description="Dữ liệu CV đã parse (CVInformation schema)"
    )
    jd_parsed: Dict[str, Any] = Field(
        ..., description="Dữ liệu JD đã parse (JDRequirements schema)"
    )


class InterviewAnswerRequest(BaseModel):
    """Request body khi ứng viên trả lời câu hỏi."""
    thread_id: str = Field(..., description="ID phiên phỏng vấn")
    answer: str = Field(..., description="Câu trả lời của ứng viên")


class InterviewResponse(BaseModel):
    """Response chung cho tất cả các endpoint interview."""
    thread_id: str
    status: str = Field(description="Trạng thái: interviewing | completed | error")
    question: Optional[str] = Field(default=None, description="Câu hỏi hiện tại (nếu đang phỏng vấn)")
    current_topic: Optional[str] = Field(default=None, description="Chủ đề đang khai thác")
    topic_index: Optional[int] = Field(default=None, description="Index chủ đề hiện tại (0-based)")
    total_topics: Optional[int] = Field(default=None, description="Tổng số chủ đề")
    final_decision: Optional[str] = Field(default=None, description="Kết quả (Pass/Fail/Consider)")
    report: Optional[str] = Field(default=None, description="Báo cáo phỏng vấn (Markdown)")
    error: Optional[str] = Field(default=None, description="Thông báo lỗi nếu có")


# ── Tên node thân thiện (hiện ra trên UI) ──
_NODE_LABELS = {
    "interview_plan_node":      "📋 Đang lập kế hoạch phỏng vấn…",
    "early_rejection_node":     "❌ Dữ liệu không hợp lệ, kết thúc sớm.",
    "question_generator_node":  "💬 Đang soạn câu hỏi…",
    "evidence_extractor_node":  "🔍 Đang phân tích câu trả lời…",
    "scoring_engine_node":      "📊 Đang chấm điểm…",
    "followup_decision_node":   "🤔 Đang quyết định hỏi thêm…",
    "followup_generator_node":  "💬 Đang soạn câu hỏi phụ…",
    "topic_completion_node":    "✅ Đang chốt chủ đề…",
    "report_generator_node":    "📝 Đang tổng hợp báo cáo…",
}


def _sse(event_type: str, data: Any) -> str:
    """Serialize một sự kiện SSE."""
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _extract_response(state: dict, thread_id: str) -> InterviewResponse:
    """Trích xuất thông tin từ state và tạo response."""
    messages = state.get("messages", [])
    topics = state.get("topics", [])
    current_idx = state.get("current_topic_index", 0)
    final_decision = state.get("final_decision")
    report = state.get("report")

    # Nếu đã có final_decision → phỏng vấn kết thúc
    if final_decision:
        return InterviewResponse(
            thread_id=thread_id,
            status="completed",
            final_decision=final_decision,
            report=report,
            total_topics=len(topics),
        )

    # Lấy câu hỏi gần nhất (AIMessage cuối cùng)
    last_question = None
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            last_question = msg.content
            break

    current_topic_name = None
    if topics and current_idx < len(topics):
        current_topic_name = topics[current_idx].get("topic_name", f"Topic {current_idx + 1}")

    return InterviewResponse(
        thread_id=thread_id,
        status="interviewing",
        question=last_question,
        current_topic=current_topic_name,
        topic_index=current_idx,
        total_topics=len(topics),
    )


# ══════════════════════════════════════════════
#  Helper: Streaming event generator
# ══════════════════════════════════════════════

async def _stream_graph(
    graph,
    input_data,
    config: dict,
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """
    Async generator phát SSE events từ LangGraph.

    Các loại event phát ra:
    - node_start   : khi một node bắt đầu chạy (kèm tên friendly)
    - llm_token    : mỗi token từ LLM (streaming)
    - done         : kết quả cuối cùng (InterviewResponse)
    - error        : khi có lỗi
    """
    final_state = None
    try:
        async for event in graph.astream_events(input_data, config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # Thông báo tiến trình node
            if kind == "on_chain_start" and name in _NODE_LABELS:
                yield _sse("node_start", {
                    "node": name,
                    "label": _NODE_LABELS[name]
                })

            # Stream token từ LLM (câu hỏi, báo cáo…)
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse("llm_token", {"token": chunk.content})

            # Bắt state cuối khi graph kết thúc
            elif kind == "on_chain_end" and name == "LangGraph":
                final_state = event.get("data", {}).get("output")

        # Phát kết quả cuối
        if final_state:
            response = _extract_response(final_state, thread_id)
            yield _sse("done", response.model_dump())
        else:
            yield _sse("error", {"message": "Không nhận được kết quả từ Graph."})

    except Exception as e:
        logger.error(f"✖ Lỗi streaming interview graph: {e}", exc_info=True)
        yield _sse("error", {"message": str(e)})


# ══════════════════════════════════════════════
#  POST /interview/start — Bắt đầu phiên phỏng vấn (JSON, không stream)
# ══════════════════════════════════════════════

@router.post(
    "/start",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Bắt đầu phiên phỏng vấn mới",
)
async def start_interview(request: InterviewStartRequest):
    """Khởi tạo phiên phỏng vấn mới với dữ liệu CV + JD đã parse."""
    thread_id = uuid.uuid4().hex

    try:
        cv_info = CVInformation.model_validate(request.cv_parsed)
        jd_info = JDRequirements.model_validate(request.jd_parsed)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dữ liệu CV/JD không hợp lệ: {str(e)}",
        )

    graph = _get_graph()

    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {"langfuse_session_id": thread_id}

    initial_state = _build_initial_state(cv_info, jd_info)

    try:
        result = await graph.ainvoke(initial_state, config)
        logger.info(f"✔ Phiên phỏng vấn {thread_id} đã khởi tạo thành công")

        if result.get("final_decision") == "Cancelled":
            return InterviewResponse(
                thread_id=thread_id,
                status="error",
                error=result.get("report", "Phỏng vấn bị hủy do lỗi dữ liệu đầu vào."),
            )

        return _extract_response(result, thread_id)

    except Exception as e:
        logger.error(f"✖ Lỗi khi khởi tạo phỏng vấn: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}",
        )


# ══════════════════════════════════════════════
#  POST /interview/start/stream — Bắt đầu phiên phỏng vấn (SSE Streaming)
# ══════════════════════════════════════════════

@router.post(
    "/start/stream",
    summary="Bắt đầu phiên phỏng vấn mới (SSE Streaming)",
    response_class=StreamingResponse,
)
async def start_interview_stream(request: InterviewStartRequest):
    """
    Khởi tạo phiên phỏng vấn mới với Server-Sent Events.

    Các sự kiện SSE client nhận được:
    - `node_start` : node bắt đầu chạy {node, label}
    - `llm_token`  : token LLM realtime {token}
    - `done`       : kết quả cuối cùng (InterviewResponse JSON)
    - `error`      : lỗi {message}

    **Quan trọng**: `thread_id` được gửi trong event `done.thread_id`.
    Client cần lưu lại để gọi `/answer/stream`.
    """
    thread_id = uuid.uuid4().hex

    try:
        cv_info = CVInformation.model_validate(request.cv_parsed)
        jd_info = JDRequirements.model_validate(request.jd_parsed)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dữ liệu CV/JD không hợp lệ: {str(e)}",
        )

    graph = _get_graph()

    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {"langfuse_session_id": thread_id}

    initial_state = _build_initial_state(cv_info, jd_info)

    return StreamingResponse(
        _stream_graph(graph, initial_state, config, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════
#  POST /interview/start_by_id — Từ ID MongoDB (JSON)
# ══════════════════════════════════════════════

@router.post(
    "/start_by_id",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Bắt đầu phiên phỏng vấn từ ID của CV và JD",
)
async def start_interview_by_id(request: InterviewStartByIdRequest):
    """Khởi tạo phiên phỏng vấn mới, tự động lấy dữ liệu từ MongoDB."""
    from src.database.mongodb import MongoDBClient

    cv_doc = await MongoDBClient.get_cv_by_id(request.cv_id)
    if not cv_doc:
        raise HTTPException(status_code=404, detail="CV không tồn tại")

    jd_doc = await MongoDBClient.get_jd_by_id(request.jd_id)
    if not jd_doc:
        raise HTTPException(status_code=404, detail="JD không tồn tại")

    start_req = InterviewStartRequest(cv_parsed=cv_doc, jd_parsed=jd_doc)
    return await start_interview(start_req)


# ══════════════════════════════════════════════
#  POST /interview/start_by_id/stream — Từ ID MongoDB (SSE)
# ══════════════════════════════════════════════

@router.post(
    "/start_by_id/stream",
    summary="Bắt đầu phiên phỏng vấn từ ID (SSE Streaming)",
    response_class=StreamingResponse,
)
async def start_interview_by_id_stream(request: InterviewStartByIdRequest):
    """SSE streaming từ CV/JD ID trong MongoDB."""
    from src.database.mongodb import MongoDBClient

    cv_doc = await MongoDBClient.get_cv_by_id(request.cv_id)
    if not cv_doc:
        raise HTTPException(status_code=404, detail="CV không tồn tại")

    jd_doc = await MongoDBClient.get_jd_by_id(request.jd_id)
    if not jd_doc:
        raise HTTPException(status_code=404, detail="JD không tồn tại")

    start_req = InterviewStartRequest(cv_parsed=cv_doc, jd_parsed=jd_doc)
    return await start_interview_stream(start_req)


# ══════════════════════════════════════════════
#  POST /interview/answer — Ứng viên trả lời (JSON)
# ══════════════════════════════════════════════

@router.post(
    "/answer",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi câu trả lời của ứng viên",
)
async def answer_question(request: InterviewAnswerRequest):
    """Gửi câu trả lời của ứng viên và tiếp tục flow phỏng vấn."""
    thread_id = request.thread_id
    graph = _get_graph()

    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {"langfuse_session_id": thread_id}

    # Kiểm tra thread tồn tại
    current_state = graph.get_state(config)
    if current_state is None or current_state.values is None or not current_state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên phỏng vấn: {thread_id}",
        )

    try:
        human_msg = HumanMessage(content=request.answer)
        await graph.aupdate_state(config, {"messages": [human_msg]})
        result = await graph.ainvoke(None, config)

        logger.info(f"✔ Phiên {thread_id}: đã xử lý câu trả lời")
        return _extract_response(result, thread_id)

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý câu trả lời phiên {thread_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}",
        )


# ══════════════════════════════════════════════
#  POST /interview/answer/stream — Ứng viên trả lời (SSE Streaming)
# ══════════════════════════════════════════════

@router.post(
    "/answer/stream",
    summary="Gửi câu trả lời của ứng viên (SSE Streaming)",
    response_class=StreamingResponse,
)
async def answer_question_stream(request: InterviewAnswerRequest):
    """
    Gửi câu trả lời và nhận phản hồi từ Agent qua Server-Sent Events.

    Các sự kiện SSE client nhận được:
    - `node_start` : node bắt đầu chạy {node, label}
    - `llm_token`  : token LLM realtime {token}
    - `done`       : kết quả cuối cùng (InterviewResponse JSON)
    - `error`      : lỗi {message}
    """
    thread_id = request.thread_id
    graph = _get_graph()

    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {"langfuse_session_id": thread_id}

    # Kiểm tra thread tồn tại trước
    current_state = graph.get_state(config)
    if current_state is None or current_state.values is None or not current_state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên phỏng vấn: {thread_id}",
        )

    # Inject câu trả lời vào state
    human_msg = HumanMessage(content=request.answer)
    await graph.aupdate_state(config, {"messages": [human_msg]})

    # Stream events từ graph (resume từ interrupt)
    return StreamingResponse(
        _stream_graph(graph, None, config, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════
#  GET /interview/status/{thread_id} — Xem trạng thái
# ══════════════════════════════════════════════

@router.get(
    "/status/{thread_id}",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem trạng thái phiên phỏng vấn",
)
async def get_interview_status(thread_id: str):
    """Lấy trạng thái hiện tại của phiên phỏng vấn (câu hỏi, topic, điểm...)."""
    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    current_state = graph.get_state(config)
    if current_state is None or current_state.values is None or not current_state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên phỏng vấn: {thread_id}",
        )

    return _extract_response(current_state.values, thread_id)


# ══════════════════════════════════════════════
#  Helper: Build initial state
# ══════════════════════════════════════════════

def _build_initial_state(cv_info: CVInformation, jd_info: JDRequirements) -> dict:
    return {
        "cv_parsed": cv_info,
        "jd_parsed": jd_info,
        "topics": [],
        "current_topic_index": 0,
        "messages": [],
        "extracted_evidence": {},
        "topic_scores": {},
        "score_reasonings": {},
        "final_decision": "",
        "report": "",
        "requires_followup": False,
        "followup_count": 0,
        "errors": [],
    }

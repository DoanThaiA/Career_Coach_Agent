import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from src.agents.interview_agent.graph import build_interview_graph
from src.agents.interview_agent.output_schema import CVInformation, JDRequirements
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
#  POST /interview/start — Bắt đầu phiên phỏng vấn
# ══════════════════════════════════════════════

from pydantic import BaseModel, Field
from typing import Any, Dict, List


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


@router.post(
    "/start",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Bắt đầu phiên phỏng vấn mới",
)
async def start_interview(request: InterviewStartRequest):
    """Khởi tạo phiên phỏng vấn mới với dữ liệu CV + JD đã parse.

    Flow:
    1. Validate CV/JD data
    2. Tạo thread_id mới
    3. Chạy graph đến interrupt (sinh câu hỏi đầu tiên)
    4. Trả về câu hỏi cho client
    """
    thread_id = uuid.uuid4().hex

    try:
        # Validate bằng Pydantic schema
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

    initial_state = {
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

    try:
        # ainvoke sẽ chạy đến interrupt_after (question_generator_node)
        result = await graph.ainvoke(initial_state, config)
        logger.info(f"✔ Phiên phỏng vấn {thread_id} đã khởi tạo thành công")

        # Kiểm tra nếu bị early_rejection
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
            detail=f"Lỗi hệ thống khi khởi tạo phỏng vấn: {str(e)}",
        )


# ══════════════════════════════════════════════
#  POST /interview/answer — Ứng viên trả lời
# ══════════════════════════════════════════════

@router.post(
    "/answer",
    response_model=InterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi câu trả lời của ứng viên",
)
async def answer_question(request: InterviewAnswerRequest):
    """Gửi câu trả lời của ứng viên và tiếp tục flow phỏng vấn.

    Flow:
    1. Inject HumanMessage vào state
    2. Resume graph (tiếp tục từ interrupt)
    3. Graph xử lý: evidence → scoring → decision → (followup hoặc next topic)
    4. Trả về câu hỏi tiếp theo hoặc kết quả cuối cùng
    """
    thread_id = request.thread_id
    graph = _get_graph()
    
    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    # Kiểm tra thread tồn tại
    current_state = graph.get_state(config)
    if current_state is None or current_state.values is None or not current_state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phiên phỏng vấn: {thread_id}",
        )

    try:
        # Inject câu trả lời vào state
        human_msg = HumanMessage(content=request.answer)
        
        # Trong LangGraph, để resume graph đang pause ở interrupt_after,
        # ta cần update state trước, sau đó gọi ainvoke(None).
        # Nếu gọi ainvoke(payload), nó sẽ start run mới từ entry point.
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
#  WS /interview/ws — Real-time Streaming
# ══════════════════════════════════════════════

@router.websocket("/ws")
async def websocket_interview_endpoint(websocket: WebSocket):
    """
    Kết nối WebSocket cho phỏng vấn.
    Client gửi JSON format:
    - Bắt đầu: {"type": "start", "payload": {"cv_parsed": {...}, "jd_parsed": {...}}}
    - Trả lời: {"type": "answer", "payload": {"thread_id": "...", "answer": "..."}}
    """
    await websocket.accept()
    logger.info("✔ Khởi tạo kết nối WebSocket thành công")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "start":
                thread_id = uuid.uuid4().hex
                try:
                    cv_info = CVInformation.model_validate(payload.get("cv_parsed", {}))
                    jd_info = JDRequirements.model_validate(payload.get("jd_parsed", {}))
                except Exception as e:
                    await websocket.send_json({"error": f"Dữ liệu CV/JD không hợp lệ: {str(e)}"})
                    continue

                graph = _get_graph()
                
                from src.core.monitoring import get_langfuse_handler
                langfuse_handler = get_langfuse_handler(session_id=thread_id)
                config = {"configurable": {"thread_id": thread_id}}
                if langfuse_handler:
                    config["callbacks"] = [langfuse_handler]

                initial_state = {
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

                try:
                    result = await graph.ainvoke(initial_state, config)
                    logger.info(f"✔ [WS] Phiên phỏng vấn {thread_id} đã khởi tạo thành công")

                    if result.get("final_decision") == "Cancelled":
                        resp = InterviewResponse(
                            thread_id=thread_id,
                            status="error",
                            error=result.get("report", "Phỏng vấn bị hủy do lỗi dữ liệu đầu vào.")
                        )
                    else:
                        resp = _extract_response(result, thread_id)
                    
                    await websocket.send_json(resp.model_dump())
                except Exception as e:
                    logger.error(f"✖ [WS] Lỗi khi khởi tạo phỏng vấn: {e}", exc_info=True)
                    await websocket.send_json({"error": f"Lỗi hệ thống: {str(e)}"})

            elif msg_type == "answer":
                thread_id = payload.get("thread_id")
                answer_text = payload.get("answer")
                
                if not thread_id or not answer_text:
                    await websocket.send_json({"error": "Thiếu thread_id hoặc answer trong payload"})
                    continue

                graph = _get_graph()
                
                from src.core.monitoring import get_langfuse_handler
                langfuse_handler = get_langfuse_handler(session_id=thread_id)
                config = {"configurable": {"thread_id": thread_id}}
                if langfuse_handler:
                    config["callbacks"] = [langfuse_handler]

                current_state = graph.get_state(config)
                if current_state is None or current_state.values is None or not current_state.values:
                    await websocket.send_json({"error": f"Không tìm thấy phiên phỏng vấn: {thread_id}"})
                    continue

                try:
                    human_msg = HumanMessage(content=answer_text)
                    await graph.aupdate_state(config, {"messages": [human_msg]})
                    
                    result = await graph.ainvoke(None, config)
                    logger.info(f"✔ [WS] Phiên {thread_id}: đã xử lý câu trả lời")
                    
                    resp = _extract_response(result, thread_id)
                    await websocket.send_json(resp.model_dump())
                except Exception as e:
                    logger.error(f"✖ [WS] Lỗi khi xử lý câu trả lời phiên {thread_id}: {e}", exc_info=True)
                    await websocket.send_json({"error": f"Lỗi hệ thống: {str(e)}"})
            
            else:
                await websocket.send_json({"error": f"Loại message không được hỗ trợ: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("✔ Client đã ngắt kết nối WebSocket")
    except Exception as e:
        logger.error(f"✖ Lỗi kết nối WebSocket: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass

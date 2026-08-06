import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from src.api.schemas import EvaluateRequest
from src.database.mongodb import MongoDBClient
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements
from src.agents.evaluation_agent.graph import get_evaluation_graph
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

# Tên node thân thiện
_NODE_LABELS = {
    "check_extraction": "🔎 Đang kiểm tra dữ liệu đầu vào…",
    "score_skills":     "🛠️ Đang chấm điểm kỹ năng…",
    "score_experience": "💼 Đang chấm điểm kinh nghiệm…",
    "score_education":  "🎓 Đang chấm điểm học vấn…",
    "generate_feedback":"💡 Đang tạo nhận xét chi tiết (LLM)…",
    "aggregate_score":  "📊 Đang tổng hợp điểm…",
    "build_output":     "📄 Đang hoàn thiện báo cáo…",
}


def _sse(event_type: str, data) -> str:
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _build_config(session_id: str) -> dict:
    from src.core.monitoring import get_langfuse_handler
    langfuse_handler = get_langfuse_handler(session_id=session_id)
    config = {}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
        config["metadata"] = {"langfuse_session_id": session_id}
    return config


async def _load_cv_jd(cv_id: str, jd_id: str):
    """Lấy và validate CV + JD từ MongoDB."""
    cv_doc = await MongoDBClient.get_cv_by_id(cv_id)
    if not cv_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV với ID: {cv_id}",
        )

    jd_doc = await MongoDBClient.get_jd_by_id(jd_id)
    if not jd_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy JD với ID: {jd_id}",
        )

    try:
        cv_parsed = CVInformation(**cv_doc)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dữ liệu CV trong DB không hợp lệ: {e}",
        )

    try:
        jd_parsed = JDRequirements(**jd_doc)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dữ liệu JD trong DB không hợp lệ: {e}",
        )

    return cv_parsed, jd_parsed


# ══════════════════════════════════════════════
#  POST /evaluation/evaluate — JSON (không stream)
# ══════════════════════════════════════════════

@router.post(
    "/evaluate",
    status_code=status.HTTP_200_OK,
    summary="Thực hiện đánh giá CV với JD (JSON)",
)
async def evaluate_candidates(request: EvaluateRequest):
    """
    Đánh giá sự phù hợp của ứng viên.
    Nhận `cv_id` và `jd_id`, trả về báo cáo đánh giá chi tiết.
    """
    logger.info(f"Yêu cầu đánh giá CV {request.cv_id} với JD {request.jd_id}")

    cv_parsed, jd_parsed = await _load_cv_jd(request.cv_id, request.jd_id)

    try:
        graph = get_evaluation_graph()
        initial_state = {"cv_parsed": cv_parsed, "jd_parsed": jd_parsed, "errors": []}

        session_id = f"eval_{request.cv_id}_{request.jd_id}"
        config = _build_config(session_id)

        result = await graph.ainvoke(initial_state, config)

        if result.get("errors"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Có lỗi trong quá trình xử lý: {result['errors']}"
            )

        eval_report = result.get("eval_report")
        if not eval_report:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Graph xử lý xong nhưng không sinh ra eval_report",
            )

        return {"status": "success", "data": eval_report.model_dump()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi hệ thống khi đánh giá: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống trong quá trình đánh giá: {e}",
        )


# ══════════════════════════════════════════════
#  POST /evaluation/evaluate/stream — SSE Streaming
# ══════════════════════════════════════════════

async def _stream_evaluation(
    cv_parsed: CVInformation,
    jd_parsed: JDRequirements,
    session_id: str,
    config: dict,
) -> AsyncGenerator[str, None]:
    """
    Async generator phát SSE events từ Evaluation Graph.

    Các loại event:
    - `node_start`  : node bắt đầu {node, label}
    - `llm_token`   : token từ LLM (generate_feedback) {token}
    - `done`        : kết quả cuối {status, data: eval_report}
    - `error`       : lỗi {message}
    """
    graph = get_evaluation_graph()
    initial_state = {"cv_parsed": cv_parsed, "jd_parsed": jd_parsed, "errors": []}
    final_output = None

    try:
        async for event in graph.astream_events(initial_state, config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # Tiến trình node
            if kind == "on_chain_start" and name in _NODE_LABELS:
                yield _sse("node_start", {
                    "node": name,
                    "label": _NODE_LABELS[name]
                })

            # Token LLM streaming (chủ yếu từ generate_feedback_node)
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse("llm_token", {"token": chunk.content})

            # Bắt state cuối khi graph kết thúc
            elif kind == "on_chain_end" and name == "LangGraph":
                final_output = event.get("data", {}).get("output")

        if final_output:
            errors = final_output.get("errors", [])
            if errors:
                yield _sse("error", {"message": f"Lỗi trong graph: {errors}"})
                return

            eval_report = final_output.get("eval_report")
            if eval_report:
                yield _sse("done", {
                    "status": "success",
                    "data": eval_report.model_dump()
                })
            else:
                yield _sse("error", {"message": "Graph hoàn tất nhưng không sinh ra eval_report."})
        else:
            yield _sse("error", {"message": "Không nhận được kết quả từ Graph."})

    except Exception as e:
        logger.error(f"✖ Lỗi streaming evaluation graph: {e}", exc_info=True)
        yield _sse("error", {"message": str(e)})


@router.post(
    "/evaluate/stream",
    summary="Đánh giá CV với JD (SSE Streaming)",
    response_class=StreamingResponse,
)
async def evaluate_candidates_stream(request: EvaluateRequest):
    """
    Đánh giá sự phù hợp của ứng viên với Server-Sent Events.

    Các sự kiện SSE client nhận được:
    - `node_start`  : node bắt đầu chạy {node, label}
    - `llm_token`   : token LLM realtime {token} (từ generate_feedback_node)
    - `done`        : kết quả cuối cùng {status, data: eval_report}
    - `error`       : lỗi {message}
    """
    logger.info(f"[Stream] Yêu cầu đánh giá CV {request.cv_id} với JD {request.jd_id}")

    cv_parsed, jd_parsed = await _load_cv_jd(request.cv_id, request.jd_id)

    session_id = f"eval_{request.cv_id}_{request.jd_id}"
    config = _build_config(session_id)

    return StreamingResponse(
        _stream_evaluation(cv_parsed, jd_parsed, session_id, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

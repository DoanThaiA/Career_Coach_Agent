from fastapi import APIRouter, HTTPException, status
from src.api.schemas import EvaluateRequest
from src.database.mongodb import MongoDBClient
from src.services.parse_cv import CVInformation
from src.services.parse_jd import JDRequirements
from src.agents.evaluation_agent.graph import get_evaluation_graph
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.post(
    "/evaluate",
    status_code=status.HTTP_200_OK,
    summary="Thực hiện đánh giá CV với JD dựa trên ID từ MongoDB",
)
async def evaluate_candidates(request: EvaluateRequest):
    """
    Endpoint đánh giá sự phù hợp của ứng viên.
    Nhận `cv_id` và `jd_id`, truy xuất dữ liệu đã bóc tách từ MongoDB,
    và trả về báo cáo đánh giá chi tiết.
    """
    logger.info(f"Yêu cầu đánh giá CV {request.cv_id} với JD {request.jd_id}")
    
    # 1. Lấy dữ liệu từ MongoDB
    cv_doc = await MongoDBClient.get_cv_by_id(request.cv_id)
    if not cv_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy CV với ID: {request.cv_id}",
        )
        
    jd_doc = await MongoDBClient.get_jd_by_id(request.jd_id)
    if not jd_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy JD với ID: {request.jd_id}",
        )
        
    # 2. Map sang Pydantic Model (Validate dữ liệu từ Mongo)
    try:
        cv_parsed = CVInformation(**cv_doc)
    except Exception as e:
        logger.error(f"Lỗi validate CV Schema cho {request.cv_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dữ liệu CV trong DB không hợp lệ: {e}",
        )
        
    try:
        jd_parsed = JDRequirements(**jd_doc)
    except Exception as e:
        logger.error(f"Lỗi validate JD Schema cho {request.jd_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dữ liệu JD trong DB không hợp lệ: {e}",
        )

    # 3. Chạy Evaluation Graph (Đồng bộ - Chờ lấy kết quả)
    try:
        graph = get_evaluation_graph()
        initial_state = {
            "cv_parsed": cv_parsed,
            "jd_parsed": jd_parsed,
            "errors": [],
        }
        
        # Invoke Graph
        result = await graph.ainvoke(initial_state)
        
        # Kiểm tra lỗi trong graph
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
            
        # Trả về dạng dict để FastAPI tự serialize ra JSON
        return {
            "status": "success",
            "data": eval_report.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi hệ thống khi đánh giá: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống trong quá trình đánh giá: {e}",
        )

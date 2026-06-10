from langchain_core.messages import AIMessage
from src.agents.interview_agent.state import InterviewState
from src.core.logger import get_logger

logger = get_logger(__name__)

async def early_rejection(state: InterviewState) -> dict:
    """Node từ chối sớm và hủy phỏng vấn khi có lỗi ở khâu đầu vào (CV/JD)."""
    logger.info(" Bắt đầu xử lý early_rejection_node ...")
    
    # 1. Lấy nguyên nhân lỗi từ State (do Node interview_plan đẩy vào)
    errors = state.get("errors", [])
    error_msg = errors[0] if isinstance(errors, list) and len(errors) > 0 else "Lỗi không xác định từ hệ thống."
    
    logger.warning(f"⚠ Phỏng vấn bị hủy do: {error_msg}")
    
    # 2. Tạo tin nhắn thông báo cho ứng viên
    reject_message = (
        f"Rất tiếc, hệ thống không thể bắt đầu buổi phỏng vấn. "
        f"Lý do: {error_msg}. "
        f"Vui lòng kiểm tra lại tài liệu (CV/JD) và bắt đầu một phiên mới."
    )
    ai_msg = AIMessage(content=reject_message)
    
    # 3. Tạo báo cáo rút gọn ghi nhận lỗi
    report_markdown = f"""
## ❌ BUỔI PHỎNG VẤN BỊ HỦY

**Quyết định:** Cancelled (Hủy bỏ)
**Lý do:** {error_msg}

*Hệ thống đã tự động dừng quá trình phỏng vấn ở khâu kiểm tra tài liệu đầu vào do không đủ dữ kiện để thiết lập kịch bản.*
    """
    
    return {
        "messages": [ai_msg],
        "final_decision": "Cancelled",
        "report": report_markdown
    }
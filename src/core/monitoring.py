from langfuse.callback import CallbackHandler
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

def get_langfuse_handler(session_id: str = None, user_id: str = None) -> CallbackHandler | None:
    """Khởi tạo CallbackHandler cho Langfuse.
    
    Trả về None nếu chưa cấu hình KEY (giúp dự án chạy bình thường kể cả khi không có Langfuse).
    """
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.debug("Bỏ qua Langfuse: chưa cấu hình PUBLIC_KEY hoặc SECRET_KEY.")
        return None
        
    logger.debug(f"Đang khởi tạo Langfuse Handler cho session: {session_id}")
    return CallbackHandler(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        session_id=session_id,
        user_id=user_id
    )

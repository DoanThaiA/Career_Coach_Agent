from langfuse.langchain import CallbackHandler
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
    
    import os
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST
    
    langfuse_handler = CallbackHandler()
    return langfuse_handler

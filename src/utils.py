from src.core.config import settings
from src.core.logger import get_logger
from langchain_openai import ChatOpenAI
from functools import lru_cache

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """LLM mặc định — dùng cho các tác vụ chung."""
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL_QWEN25,
        temperature=0.7,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,
    )


@lru_cache(maxsize=1)
def get_extraction_llm() -> ChatOpenAI:
    """LLM cho extraction (CV/JD parsing).
    
    Dùng temperature thấp để đảm bảo bóc tách chính xác,
    không hallucinate dữ liệu.
    """
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL_QWEN25,
        temperature=0.1,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=False,
    )


@lru_cache(maxsize=1)
def get_evaluation_llm() -> ChatOpenAI:
    """LLM cho evaluation (đánh giá CV vs JD).
    
    Dùng temperature vừa phải để cân bằng giữa
    sáng tạo (viết lại CV) và chính xác (chấm điểm).
    """
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL_QWEN25,
        temperature=0.3,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=False,
    )

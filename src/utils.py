from src.core.config import settings
from src.core.logger import get_logger
from langchain_cohere import ChatCohere
from pydantic import BaseModel
from functools import lru_cache
from typing import TypeVar, Type, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
import json
import re

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def parse_llm_json(text: str, schema: Type[T]) -> T:
    """Parse JSON output từ LLM với error handling robust.
    
    Xử lý các trường hợp phổ biến:
    - JSON bọc trong ```json ... ```
    - JSON bọc trong ``` ... ```
    - Trailing comma trước }
    - Text thừa trước/sau JSON
    
    Args:
        text: Raw text từ LLM response
        schema: Pydantic model class để validate
        
    Returns:
        Instance của schema đã validate
        
    Raises:
        ValueError: Nếu không parse được JSON hợp lệ
    """
    if not text or not text.strip():
        raise ValueError("LLM trả về response rỗng")
    
    # Loại bỏ thẻ <think>...</think> nếu có (thường gặp ở các mô hình reasoning)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    original_text = text
    
    # 1. Thử parse trực tiếp (trường hợp LLM trả pure JSON)
    try:
        data = json.loads(text, strict=False)
        return schema.model_validate(data)
    except (json.JSONDecodeError, Exception):
        pass
    
    # 2. Tìm JSON trong markdown code block ```json ... ``` hoặc ``` ... ```
    patterns = [
        r'```json\s*\n?(.*?)\n?\s*```',  # ```json ... ```
        r'```\s*\n?(.*?)\n?\s*```',       # ``` ... ```
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                data = json.loads(json_str, strict=False)
                return schema.model_validate(data)
            except json.JSONDecodeError:
                # Thử fix trailing comma
                fixed = _fix_trailing_commas(json_str)
                try:
                    data = json.loads(fixed, strict=False)
                    return schema.model_validate(data)
                except (json.JSONDecodeError, Exception):
                    pass
    
    # 3. Tìm JSON object {...} trong text
    json_str = _extract_json_object(text)
    if json_str:
        try:
            data = json.loads(json_str, strict=False)
            return schema.model_validate(data)
        except json.JSONDecodeError:
            fixed = _fix_trailing_commas(json_str)
            try:
                data = json.loads(fixed, strict=False)
                return schema.model_validate(data)
            except (json.JSONDecodeError, Exception):
                pass
    
    # 4. Không parse được — raise error với context
    # Cắt text để log không quá dài
    preview = original_text[:500] + "..." if len(original_text) > 500 else original_text
    raise ValueError(
        f"Không thể parse JSON từ LLM output.\n"
        f"Output preview: {preview}"
    )


def _fix_trailing_commas(json_str: str) -> str:
    """Xóa trailing commas trước } và ] (lỗi phổ biến của LLM)."""
    # ,} → }
    json_str = re.sub(r',\s*}', '}', json_str)
    # ,] → ]
    json_str = re.sub(r',\s*]', ']', json_str)
    return json_str


def _extract_json_object(text: str) -> str | None:
    """Tìm và trích xuất JSON object {...} từ text.
    
    Sử dụng bracket counting để tìm đúng closing brace.
    """
    start = text.find('{')
    if start == -1:
        return None
    
    depth = 0
    in_string = False
    escape = False
    
    for i in range(start, len(text)):
        char = text[i]
        
        if escape:
            escape = False
            continue
        
        if char == '\\':
            escape = True
            continue
            
        if char == '"' and not escape:
            in_string = not in_string
            continue
            
        if in_string:
            continue
            
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    
    # Nếu không tìm được closing brace (JSON bị cắt), trả về phần có
    # và thử close nó
    remaining = text[start:]
    if depth > 0:
        # Thêm closing braces
        remaining += '}' * depth
        logger.warning(f"⚠ JSON bị cắt (truncated), thử tự đóng {depth} ngoặc")
    return remaining


async def generate_with_retry_and_correction(
    llm, 
    prompt: str, 
    schema_class: Type[T], 
    max_retries: int = 3,
    callbacks: Optional[List[BaseCallbackHandler]] = None
) -> T:
    """Gọi LLM và parse JSON, nếu lỗi sẽ feed lỗi ngược lại để LLM tự sửa.
    
    Đây là cơ chế Self-Correction giúp LLM học từ lỗi và sửa trực tiếp,
    tăng độ ổn định đáng kể thay vì chỉ retry mù quáng.
    """
    current_prompt = prompt
    last_error = None
    
    for attempt in range(max_retries):
        try:
            config = {"callbacks": callbacks} if callbacks else None
            response = await llm.ainvoke(current_prompt, config=config)
            raw_text = response.content
            logger.debug(f"LLM raw output ({len(raw_text)} chars) - Attempt {attempt+1}")
            return parse_llm_json(raw_text, schema_class)
        except Exception as e:
            last_error = e
            logger.warning(f"⚠ Lỗi parse JSON lần {attempt+1}/{max_retries}: {e}")
            
            # Nếu còn lượt retry, tạo prompt sửa lỗi
            if attempt < max_retries - 1:
                correction_instruction = (
                    f"\n\n[HỆ THỐNG]: Lần chạy trước bạn trả về JSON bị lỗi schema/format. "
                    f"Lỗi chi tiết: {str(e)}\n"
                    f"Hãy xem xét kỹ output trước đó của bạn và SỬA LẠI cho đúng. "
                    f"CHỈ trả về JSON hợp lệ, không kèm text giải thích."
                )
                
                # Nếu LLM trả về một đoạn text nào đó, kèm nó vào để nó biết nó vừa viết gì
                if 'response' in locals() and response.content:
                    # Giới hạn độ dài để không tràn context
                    failed_output = response.content[:1500] + "..." if len(response.content) > 1500 else response.content
                    current_prompt = prompt + f"\n\n[OUTPUT BỊ LỖI CỦA BẠN TRƯỚC ĐÓ]:\n{failed_output}" + correction_instruction
                else:
                    current_prompt = prompt + correction_instruction

    logger.error(f"✖ Không thể sửa lỗi JSON sau {max_retries} lần thử.")
    raise last_error



def get_schema_instruction(schema_class: Type[T]) -> str:
    """Tạo hướng dẫn JSON schema từ Pydantic model.
    
    Hàm dùng chung cho tất cả nodes để tránh copy-paste.
    """
    schema = schema_class.model_json_schema()
    return (
        "\n\nTrả kết quả dưới dạng JSON hợp lệ theo schema sau. "
        "CHỈ trả pure JSON object, KHÔNG bọc trong ```json``` hay thêm text nào khác.\n"
        f"{json.dumps(schema, indent=2, ensure_ascii=False)}"
    )


@lru_cache(maxsize=1)
def get_llm() -> ChatCohere:
    """LLM mặc định — dùng cho các tác vụ chung (chat, Q&A)."""
    return ChatCohere(
        cohere_api_key=settings.COHERE_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.7,
    )


@lru_cache(maxsize=1)
def get_extraction_llm() -> ChatCohere:
    """LLM cho extraction (CV/JD parsing).
    
    - streaming=False: bắt buộc cho structured output trên LLM local.
    - temperature=0.1: bóc tách chính xác, không hallucinate.
    - max_tokens cao hơn mặc định vì JSON output có thể dài.
    """
    return ChatCohere(
        cohere_api_key=settings.COHERE_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.1,
    )


@lru_cache(maxsize=1)
def get_evaluation_llm() -> ChatCohere:
    """LLM cho evaluation (đánh giá CV vs JD).
    
    - streaming=False: bắt buộc cho structured output.
    - temperature=0.3: cân bằng sáng tạo và chính xác.
    - max_tokens cao vì EvaluationReport JSON rất dài.
    """
    return ChatCohere(
        cohere_api_key=settings.COHERE_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )

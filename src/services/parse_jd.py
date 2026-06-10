from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from src.core.logger import get_logger
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction

logger = get_logger(__name__)

class SkillPriority(str, Enum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class JDSkill(BaseModel):
    name: str = Field(description="Tên kỹ năng/công nghệ yêu cầu")
    priority: SkillPriority = Field(description="Mức độ ưu tiên: must_have hoặc nice_to_have")
    min_yoe: Optional[float] = Field(
        default=None, description="Số năm kinh nghiệm tối thiểu cho kỹ năng này (nếu có)"
    )


class JDRequirements(BaseModel):
    job_title: str = Field(description="Tên vị trí tuyển dụng")
    level: Optional[str] = Field(
        default=None, description="Cấp bậc (Junior, Mid, Senior, Lead, Manager)"
    )
    skills: List[JDSkill] = Field(description="Danh sách kỹ năng yêu cầu kèm mức ưu tiên")
    min_years_experience: Optional[float] = Field(
        default=None, description="Tổng số năm kinh nghiệm tối thiểu"
    )
    education_requirements: Optional[str] = Field(
        default=None, description="Yêu cầu học vấn (VD: Cử nhân CNTT)"
    )
    responsibilities: Optional[List[str]] = Field(
        default=None, description="Các trách nhiệm chính của vị trí"
    )
    benefits_summary: Optional[str] = Field(
        default=None, description="Tóm tắt quyền lợi (nếu có)"
    )

PARSE_JD_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Chuyên gia Phân tích Yêu cầu Tuyển dụng (Expert Job Description Analyst).
Nhiệm vụ của bạn là đọc mô tả công việc (JD) và bóc tách thành dữ liệu có cấu trúc.

HƯỚNG DẪN BẮT BUỘC:

1. PHÂN LOẠI KỸ NĂNG THEO MỨC ĐỘ ƯU TIÊN:
   - "must_have": Kỹ năng bắt buộc phải có. Nhận biết qua các từ khóa: "yêu cầu", "bắt buộc", "cần có", "required", "must have", hoặc nếu kỹ năng xuất hiện trong phần "Yêu cầu chính".
   - "nice_to_have": Kỹ năng ưu tiên/tham khảo. Nhận biết qua: "ưu tiên", "preferred", "nice to have", "là một lợi thế", "plus".
   - Nếu JD không phân biệt rõ ràng, hãy dùng tư duy của chuyên gia để phán đoán dựa trên tầm quan trọng của kỹ năng đối với vị trí.

2. TÍNH TOÁN SỐ NĂM KINH NGHIỆM:
   - Trích xuất min_years_experience nếu JD ghi rõ (VD: "3+ năm kinh nghiệm").
   - Trích xuất min_yoe cho từng kỹ năng nếu có (VD: "2 năm kinh nghiệm với Python").

3. NGUYÊN TẮC SỰ THẬT:
   - CHỈ trích xuất thông tin có thật trong JD. KHÔNG tự thêm kỹ năng hoặc yêu cầu.
   - Nếu thông tin không có, trả về null.

Hãy phân tích JD dưới đây:
{jd_context}

═══════════════════════════════════════════
VÍ DỤ MẪU (FEW-SHOT EXAMPLE)
═══════════════════════════════════════════
[Input JD (Trích đoạn)]:
Tuyển dụng Backend Developer (2+ năm kinh nghiệm).
Yêu cầu bắt buộc: Python, SQL.
Ưu tiên: Có kinh nghiệm Docker là một lợi thế.

[Output JSON mong đợi (Minh họa cấu trúc)]:
{{
  "job_title": "Backend Developer",
  "min_years_experience": 2.0,
  "skills": [
    {{ "name": "Python", "priority": "must_have", "min_yoe": 2.0 }},
    {{ "name": "SQL", "priority": "must_have", "min_yoe": null }},
    {{ "name": "Docker", "priority": "nice_to_have", "min_yoe": null }}
  ]
}}
""")

async def parse_jd(jd_context: str, callbacks=None) -> JDRequirements | dict:
    logger.info(" Bắt đầu xử lý extractor_node ...")

    try:
        llm = get_extraction_llm()
        prompt = PARSE_JD_PROMPT.format(jd_context=jd_context) + get_schema_instruction(JDRequirements)
        jd_parsed = await generate_with_retry_and_correction(llm, prompt, JDRequirements, max_retries=3, callbacks=callbacks)

        if not jd_parsed.skills:
            logger.warning("⚠ JD được parse nhưng không có kỹ năng")

        logger.info("✔ Xử lý extractor_node thành công")
        return jd_parsed

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi bóc tách CV: {str(e)}"]}
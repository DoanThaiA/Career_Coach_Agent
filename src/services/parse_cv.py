from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from src.core.logger import get_logger
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
class Certification(BaseModel):
    name: Optional[str] = Field(default=None, description="Tên chứng chỉ")
    issuer: Optional[str] = Field(default=None, description="Đơn vị cấp chứng chỉ")
    issue_date: Optional[str] = Field(default=None, description="Ngày cấp hoặc năm cấp")


class Education(BaseModel):
    degree: Optional[str] = Field(default=None, description="Bằng cấp (VD: Cử nhân, Thạc sĩ)")
    major: Optional[str] = Field(default=None, description="Chuyên ngành")
    institution: Optional[str] = Field(default=None, description="Trường học")
    graduation_year: Optional[str] = Field(default=None, description="Năm tốt nghiệp")
    gpa: Optional[str] = Field(default=None, description="Điểm trung bình (nếu có)")


class ExtractedSkill(BaseModel):
    name: str = Field(description="Tên kỹ năng (VD: Python, Giao tiếp, ReactJS)")
    context: Optional[str] = Field(
        default=None,
        description="Tóm tắt ngắn gọn ứng viên đã dùng kỹ năng này để làm gì trong CV"
    )
    yoe: Optional[float] = Field(
        default=None,
        description="Số năm kinh nghiệm ước tính sử dụng kỹ năng này (nếu suy luận được)"
    )


class Skill(BaseModel):
    hard_skills: Optional[List[ExtractedSkill]] = Field(
        default=None, description="Các kỹ năng chuyên môn/nghiệp vụ"
    )
    soft_skills: Optional[List[ExtractedSkill]] = Field(
        default=None, description="Các kỹ năng mềm"
    )
    technical_skills: Optional[List[ExtractedSkill]] = Field(
        default=None, description="Các công nghệ, ngôn ngữ lập trình, framework"
    )
    languages: Optional[List[str]] = Field(
        default=None, description="Ngoại ngữ (VD: Tiếng Anh - IELTS 7.0)"
    )


class ResponsibilityDetail(BaseModel):
    action: Optional[str] = Field(
        default=None, description="Hành động ứng viên đã làm"
    )
    metrics_or_results: Optional[str] = Field(
        default=None,
        description="Kết quả đạt được (số liệu, tỷ lệ, quy mô). Trả về null nếu không có."
    )


class WorkExperience(BaseModel):
    title: Optional[str] = Field(default=None, description="Chức danh")
    company: Optional[str] = Field(default=None, description="Công ty")
    start_date: Optional[str] = Field(default=None, description="Ngày/Tháng/Năm bắt đầu")
    end_date: Optional[str] = Field(
        default=None, description="Ngày/Tháng/Năm kết thúc (hoặc 'Hiện tại')"
    )
    responsibilities: Optional[List[ResponsibilityDetail]] = Field(
        default=None, description="Chi tiết công việc và kết quả"
    )


class Project(BaseModel):
    name: Optional[str] = Field(default=None, description="Tên dự án")
    description: Optional[str] = Field(default=None, description="Mô tả dự án và kết quả")
    role: Optional[str] = Field(default=None, description="Vai trò trong dự án")
    technologies: Optional[List[str]] = Field(
        default=None, description="Các công nghệ/công cụ được sử dụng trong dự án này"
    )


class CVInformation(BaseModel):
    full_name: Optional[str] = Field(default=None, description="Họ tên ứng viên")
    email: Optional[str] = Field(default=None, description="Email liên hệ")
    phone: Optional[str] = Field(default=None, description="Số điện thoại")
    total_yoe: Optional[float] = Field(
        default=None,
        description="Tổng số năm kinh nghiệm tính toán từ các mốc thời gian làm việc"
    )
    education: Optional[List[Education]] = Field(
        default=None, description="Danh sách thông tin học vấn"
    )
    work_experience: Optional[List[WorkExperience]] = Field(
        default=None, description="Danh sách kinh nghiệm làm việc"
    )
    skills: Optional[Skill] = Field(default=None, description="Tổng hợp kỹ năng")
    projects: Optional[List[Project]] = Field(
        default=None, description="Danh sách các dự án"
    )
    certifications: Optional[List[Certification]] = Field(
        default=None, description="Danh sách các chứng chỉ chuyên môn"
    )

EXTRACT_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Hệ thống Bóc tách Dữ liệu Nhân sự (Expert HR Data Parser) cấp độ chuyên gia.
Nhiệm vụ của bạn là đọc văn bản thô từ CV của ứng viên và chuyển đổi nó thành cấu trúc dữ liệu JSON chặt chẽ, chính xác tuyệt đối.

HƯỚNG DẪN TƯ DUY VÀ XỬ LÝ DỮ LIỆU (BẮT BUỘC TUÂN THỦ):

1. NGUYÊN TẮC SỰ THẬT (ZERO HALLUCINATION):
- CHỈ trích xuất thông tin có thực trong văn bản được cung cấp.
- KHÔNG tự động suy diễn, KHÔNG tự thêm thắt kỹ năng, KHÔNG đoán mò số liệu. 
- Nếu một trường dữ liệu (field) không có thông tin trong CV, hãy trả về `null` hoặc mảng rỗng `[]`. Tuyệt đối không bịa data để điền vào cho đủ.

2. THÔNG TIN CƠ BẢN:
- Trích xuất họ tên (full_name), email, số điện thoại (phone) nếu có.
- Tính toán total_yoe (tổng số năm kinh nghiệm) dựa trên các mốc thời gian làm việc.

3. BÓC TÁCH KỸ NĂNG (SKILL EXTRACTION):
- Đừng chỉ liệt kê tên kỹ năng. Hãy đọc kỹ phần mô tả dự án và kinh nghiệm để tổng hợp "Ngữ cảnh sử dụng" (context).
- Ví dụ: Ứng viên ghi "Sử dụng Python để viết API", hãy ghi nhận context là "Viết API backend". 
- Tự động phân loại kỹ năng vào các nhóm phù hợp: hard_skills (chuyên môn), technical_skills (công nghệ, ngôn ngữ lập trình, framework), soft_skills (kỹ năng mềm).
- Ước lượng yoe (số năm kinh nghiệm) cho từng kỹ năng nếu có thể suy luận từ timeline làm việc.

4. TÍNH TOÁN THỜI GIAN (TIME CALCULATION):
- Khi gặp các mốc thời gian làm việc (ví dụ: "01/2022 - 05/2023" hoặc "Jan 2022 to Present"), hãy tự động tính toán tổng số tháng/năm kinh nghiệm.
- Coi mốc "Present" hoặc "Hiện tại" là thời điểm hiện tại (Tháng 6/2026).

5. QUY TẮC BÓC TÁCH KINH NGHIỆM LÀM VIỆC (WORK EXPERIENCE):
- Hãy "phẫu thuật" từng gạch đầu dòng trong kinh nghiệm làm việc của ứng viên thành 2 phần tách biệt: Hành động (Action) và Số liệu đo lường (Metrics/Results).
- Nếu ứng viên viết: "Tối ưu hóa truy vấn SQL giúp giảm 30% thời gian tải", hãy tách `action`: "Tối ưu hóa truy vấn SQL", và `metrics`: "Giảm 30% thời gian tải".
- [QUAN TRỌNG] Nếu câu văn chỉ là liệt kê trách nhiệm chung chung (ví dụ: "Phát triển tính năng mới"), hãy đặt trường `metrics_or_results` là `null`. Hệ thống cần điều này để đánh giá độ chuyên nghiệp của CV.

Hãy tập trung, đọc kỹ từng dòng văn bản CV dưới đây và bắt đầu bóc tách:
{cv_context}

═══════════════════════════════════════════
VÍ DỤ MẪU (FEW-SHOT EXAMPLE)
═══════════════════════════════════════════
[Input CV (Trích đoạn)]:
John Doe | 0901234567
Kinh nghiệm: Backend Dev tại ABC (01/2021 - 12/2022). Phát triển API với FastAPI phục vụ 1000 users.
Kỹ năng: Python, Docker.

[Output JSON mong đợi (Minh họa cấu trúc)]:
{{
  "full_name": "Neymar Jr",
  "phone": "0901234567",
  "total_yoe": 5.0,
  "work_experience": [
    {{
      "title": "DEV ", "company": "ABC", "start_date": "01/2021", "end_date": "12/2022",
      "responsibilities": [
        {{ "action": "Phát triển API với FastAPI", "metrics_or_results": "phục vụ 1000 users" }}
      ]
    }}
  ],
  "skills": {{
    "technical_skills": [
      {{ "name": "Python", "context": "Backend", "yoe": 2.0 }},
      {{ "name": "FastAPI", "context": "Phát triển API", "yoe": 2.0 }},
      {{ "name": "Docker", "context": null, "yoe": null }}
    ]
  }}
}}
""")



logger = get_logger(__name__)


async def parse_cv(cv_content: str, callbacks=None) -> CVInformation | dict:
    """Node bóc tách CV: text thô → CVInformation (structured).
    
    Gọi LLM trực tiếp và parse JSON thủ công thay vì dùng
    with_structured_output (không tương thích LLM server local).
    """
    logger.info("▶ Bắt đầu xử lý extractor_node ...")

    if not cv_content:
        logger.warning("✖ Không tìm thấy nội dung CV")
        return {"errors": ["Không tìm thấy nội dung CV"]}

    if not cv_content.strip():
        logger.warning("✖ Nội dung CV rỗng")
        return {"errors": ["Nội dung CV rỗng"]}

    try:
        llm = get_extraction_llm()
        prompt = EXTRACT_PROMPT.format(cv_context=cv_content) + get_schema_instruction(CVInformation)
        cv_parsed = await generate_with_retry_and_correction(
            llm, prompt, CVInformation, max_retries=3, callbacks=callbacks
        )

        if not cv_parsed.work_experience and not cv_parsed.skills and not cv_parsed.education:
            logger.warning("CV được parse nhưng không có dữ liệu quan trọng")

        logger.info("✔ Xử lý extractor_node thành công")
        return cv_parsed

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node: {e}", exc_info=True)
        raise e



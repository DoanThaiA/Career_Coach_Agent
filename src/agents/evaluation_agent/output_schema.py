from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ──────────────────────────────────────────────
# CV Extraction Schemas
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# JD Parsing Schemas
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Evaluation Report Schemas
# ──────────────────────────────────────────────

class Recommendation(str, Enum):
    PASS = "PASS"
    CONSIDER = "CONSIDER"
    REJECT = "REJECT"


class SkillMatch(BaseModel):
    skill_name: str = Field(description="Tên kỹ năng từ JD")
    matched: bool = Field(description="Ứng viên có kỹ năng này không (hoặc kỹ năng tương đương)")
    cv_evidence: Optional[str] = Field(
        default=None,
        description="Bằng chứng cụ thể từ CV chứng minh ứng viên có kỹ năng này"
    )
    equivalent_skill: Optional[str] = Field(
        default=None,
        description="Tên kỹ năng tương đương mà ứng viên có (nếu không match trực tiếp)"
    )
    is_must_have: bool = Field(description="Đây là kỹ năng bắt buộc hay nice-to-have")
    score: float = Field(ge=0, le=10, description="Điểm đánh giá 0-10 cho kỹ năng này")
    note: Optional[str] = Field(default=None, description="Ghi chú thêm về kỹ năng")


class ExperienceFeedback(BaseModel):
    company: Optional[str] = Field(default=None, description="Tên công ty liên quan")
    original_text: str = Field(description="Câu/đoạn gốc từ CV")
    issue: str = Field(
        description="Vấn đề phát hiện được (thiếu metrics, quá chung chung, thiếu action verb, ...)"
    )
    has_metrics: bool = Field(description="Câu có chứa số liệu đo lường cụ thể không")
    impact_score: float = Field(ge=0, le=10, description="Điểm đánh giá mức độ impact 0-10")


class RewriteSuggestion(BaseModel):
    original_text: str = Field(description="Câu gốc cần viết lại")
    rewritten_text: str = Field(
        description="Câu đã viết lại theo công thức XYZ (Đạt được X, bằng cách Y, dẫn đến kết quả Z)"
    )
    improvement_reason: str = Field(description="Giải thích ngắn gọn tại sao câu mới tốt hơn")


class CategoryScore(BaseModel):
    category: str = Field(description="Tên hạng mục đánh giá")
    score: float = Field(ge=0, le=100, description="Điểm 0-100")
    weight: float = Field(ge=0, le=1, description="Trọng số (0-1)")
    weighted_score: float = Field(ge=0, le=100, description="Điểm có trọng số")
    feedback: str = Field(description="Nhận xét chi tiết cho hạng mục này")


class EvaluationReport(BaseModel):
    overall_score: float = Field(ge=0, le=100, description="Điểm tổng 0-100")
    recommendation: Recommendation = Field(
        description="Khuyến nghị: PASS (>=70), CONSIDER (50-69), REJECT (<50)"
    )
    score_breakdown: List[CategoryScore] = Field(
        description="Chi tiết điểm theo từng hạng mục"
    )
    skill_analysis: List[SkillMatch] = Field(
        description="Phân tích chi tiết từng kỹ năng"
    )
    experience_feedback: List[ExperienceFeedback] = Field(
        description="Nhận xét về từng mục kinh nghiệm"
    )
    rewrite_suggestions: List[RewriteSuggestion] = Field(
        description="Đề xuất viết lại các câu yếu trong CV"
    )
    education_fit: Optional[str] = Field(
        default=None, description="Đánh giá mức độ phù hợp của học vấn"
    )
    experience_level_match: Optional[str] = Field(
        default=None,
        description="Đánh giá số năm kinh nghiệm so với yêu cầu JD"
    )
    strengths: List[str] = Field(
        description="Danh sách điểm mạnh nổi bật của ứng viên"
    )
    weaknesses: List[str] = Field(
        description="Danh sách điểm yếu/thiếu sót chính"
    )
    final_conclusion: str = Field(
        description="Kết luận tổng thể về mức độ phù hợp của ứng viên"
    )

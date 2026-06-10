from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


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

class Topic(BaseModel):
    topic_name: str = Field(
        description="Tên chủ đề phỏng vấn rõ ràng. VD: Kinh nghiệm tối ưu hiệu năng ReactJS"
    )
    context_source: str = Field(
        description="Phân tích lý do chọn chủ đề này dựa trên sự đối chiếu giữa CV và JD. Điểm khớp hoặc điểm thiếu hụt là gì?"
    )
    expected_outcome: str = Field(
        description="Đầu ra kỳ vọng cho câu trả lời của ứng viên, hoặc framework cần dùng (VD: Dùng mô hình STAR để kiểm tra kỹ năng giải quyết xung đột)"
    )
class InterviewPlan(BaseModel):
    topics: List[Topic] = Field(
        description="Danh sách từ 3 đến 5 chủ đề cốt lõi nhất cần khai thác trong buổi phỏng vấn"
    )
class ExtractedEvidence(BaseModel):
    key_points: List[str] = Field(
        description="Các ý chính, công nghệ, hoặc thành tựu mà ứng viên vừa nhắc đến trong câu trả lời."
    )
    is_off_topic: bool = Field(
        description="Đánh dấu True nếu câu trả lời của ứng viên hoàn toàn lạc đề hoặc lảng tránh câu hỏi."
    )

class TopicScoreResult(BaseModel):
    score: int = Field(
        description="Điểm số đánh giá từ 1 đến 10 dựa trên mức độ đáp ứng yêu cầu của JD."
    )
    reasoning: str = Field(
        description="Phân tích và giải thích chi tiết tại sao lại cho mức điểm này. Chỉ ra điểm tốt và điểm thiếu hụt dựa trên bằng chứng."
    )

class TopicFeedback(BaseModel):
    topic_name: str = Field(description="Tên chủ đề đánh giá")
    score: int = Field(description="Điểm số đạt được (1-10)")
    feedback: str = Field(description="Nhận xét chi tiết: Ứng viên đã làm tốt điểm nào và hổng kiến thức ở đâu.")

class FinalInterviewReport(BaseModel):
    overall_score: float = Field(
        description="Điểm đánh giá tổng quan trung bình trên thang 10 (Làm tròn 1 chữ số thập phân)."
    )
    final_decision: str = Field(
        description="Quyết định: 'Pass' (Đạt), 'Fail' (Chưa đạt), hoặc 'Consider' (Cân nhắc thêm)."
    )
    executive_summary: str = Field(
        description="Tóm tắt ngắn gọn (khoảng 3-4 câu) về sự thể hiện tổng thể của ứng viên so với JD."
    )
    topic_evaluations: List[TopicFeedback] = Field(
        description="Đánh giá lại chi tiết từng chủ đề đã phỏng vấn."
    )
    key_strengths: List[str] = Field(
        description="Liệt kê 2-3 năng lực cốt lõi mạnh nhất của ứng viên."
    )
    critical_gaps: List[str] = Field(
        description="Liệt kê các lỗ hổng kiến thức nghiêm trọng nhất so với JD."
    )
    learning_path: List[str] = Field(
        description="Gợi ý lộ trình hành động (Actionable Advice): Ứng viên cần học thêm công nghệ gì, tìm hiểu khái niệm nào để khắc phục lỗ hổng."
    )
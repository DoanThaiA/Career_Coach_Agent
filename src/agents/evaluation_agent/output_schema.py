from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


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


class SkillEvaluationResult(BaseModel):
    skill_analysis: List[SkillMatch] = Field(
        description="Phân tích chi tiết từng kỹ năng"
    )
    score_breakdown: List[CategoryScore] = Field(
        description="Chi tiết điểm cho các hạng mục kỹ năng (Must-have, Nice-to-have)"
    )


class ExperienceEvaluationResult(BaseModel):
    experience_feedback: List[ExperienceFeedback] = Field(
        description="Nhận xét về từng mục kinh nghiệm"
    )
    rewrite_suggestions: List[RewriteSuggestion] = Field(
        description="Đề xuất viết lại các câu yếu trong CV"
    )
    score_breakdown: List[CategoryScore] = Field(
        description="Chi tiết điểm cho hạng mục Kinh nghiệm"
    )
    experience_level_match: Optional[str] = Field(
        default=None,
        description="Đánh giá số năm kinh nghiệm so với yêu cầu JD"
    )



class FinalSynthesis(BaseModel):
    """Schema gọn cho eval_final_node.
    
    LLM chỉ cần sinh phần tổng hợp mới (strengths, weaknesses, conclusion,
    education scoring). Phần skill_analysis và experience_feedback sẽ được
    copy bằng Python code từ state, không qua LLM.
    """
    overall_score: float = Field(ge=0, le=100, description="Điểm tổng 0-100")
    recommendation: Recommendation = Field(
        description="Khuyến nghị: PASS (>=70), CONSIDER (50-69), REJECT (<50)"
    )
    score_breakdown: List[CategoryScore] = Field(
        description="Chi tiết điểm cho Học vấn & Trình bày (chỉ phần chưa có)"
    )
    education_fit: Optional[str] = Field(
        default=None, description="Đánh giá mức độ phù hợp của học vấn"
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

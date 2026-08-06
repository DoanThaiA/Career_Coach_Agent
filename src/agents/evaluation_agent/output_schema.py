from pydantic import BaseModel, Field
from typing import List, Optional

class ImprovementSuggestion(BaseModel):
    area: str = Field(description="Khía cạnh cần cải thiện, vd: 'Kỹ năng', 'Cách trình bày thành tựu'")
    suggestion: str = Field(description="Gợi ý cụ thể, actionable - không nói chung chung")

class FeedbackAssessment(BaseModel):
    qualitative_score: float = Field(
        description="Điểm phù hợp định tính (0-100), dựa trên mức độ liên quan của kinh nghiệm/thành tựu thực tế so với trách nhiệm công việc JD yêu cầu"
    )
    overall_impression: str = Field(description="Nhận xét tổng quan 2-3 câu, giọng khích lệ và trung thực")
    strengths: List[str] = Field(description="Điểm mạnh của ứng viên nên giữ/nhấn mạnh")
    improvement_suggestions: List[ImprovementSuggestion] = Field(
        description="Gợi ý cải thiện cụ thể để tăng độ phù hợp với JD này"
    )

class CategoryScore(BaseModel):
    category: str = Field(description="Tên hạng mục đánh giá")
    score: float = Field(description="Điểm 0-100")
    weight: float = Field(description="Trọng số (0-1)")
    weighted_score: float = Field(description="Điểm có trọng số")
    feedback: str = Field(description="Nhận xét chi tiết cho hạng mục này")

class EvaluationReport(BaseModel):
    match_score: float = Field(description="Điểm tổng 0-100")
    fit_level: str = Field(description="Đánh giá mức độ phù hợp bằng chữ")
    breakdown: dict = Field(description="Chi tiết điểm số (skill, experience, education, qualitative)")
    matched_skills: List[str] = Field(default_factory=list, description="Kỹ năng match")
    missing_skills: List[str] = Field(default_factory=list, description="Kỹ năng còn thiếu")
    missing_must_have_skills: List[str] = Field(default_factory=list, description="Kỹ năng bắt buộc còn thiếu")
    overall_impression: str = Field(description="Nhận xét tổng quan")
    strengths: List[str] = Field(default_factory=list, description="Danh sách điểm mạnh")
    improvement_suggestions: List[dict] = Field(default_factory=list, description="Gợi ý cải thiện")

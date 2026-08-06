from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum




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
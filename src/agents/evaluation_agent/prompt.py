from langchain_core.prompts import ChatPromptTemplate



EVAL_SKILLS_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Chuyên gia Đánh giá Kỹ năng Tuyển dụng IT.
Nhiệm vụ của bạn là đối chiếu kỹ năng của ứng viên (CV đã bóc tách) với yêu cầu công việc (JD đã phân tích).

═══════════════════════════════════════════
RUBRIC CHẤM ĐIỂM KỸ NĂNG (Tổng 55 điểm)
═══════════════════════════════════════════
- Must-have Skills (40đ): Mỗi kỹ năng thiếu -10đ. Kỹ năng tương đương -3đ.
- Nice-to-have Skills (15đ): Mỗi kỹ năng có +3đ.

NGUYÊN TẮC:
1. KỸ NĂNG TƯƠNG ĐƯƠNG: Nếu JD yêu cầu kỹ năng A, nhưng CV có kỹ năng B cùng hệ sinh thái (VD: NextJS ≈ ReactJS), ghi rõ vào `equivalent_skill`.
2. Trả về `matched = false` nếu hoàn toàn không có kỹ năng liên quan.

### JD đã phân tích:
{jd_data}

### CV đã bóc tách:
{cv_data}

Trả về danh sách đối chiếu từng kỹ năng và điểm thành phần theo đúng schema.

═══════════════════════════════════════════
VÍ DỤ MẪU (FEW-SHOT EXAMPLE - TRÍCH ĐOẠN ĐẦU RA JSON)
═══════════════════════════════════════════
{{
  "skill_analysis": [
    {{
      "skill_name": "Python", "matched": true, "is_must_have": true, 
      "score": 10.0, "cv_evidence": "Có 2 năm kinh nghiệm làm Backend Python"
    }}
  ],
  "score_breakdown": [
    {{
      "category": "Must-have Skills", "score": 100.0, "weight": 0.4, "weighted_score": 40.0,
      "feedback": "Đáp ứng đầy đủ kỹ năng bắt buộc."
    }}
  ]
}}
""")


EVAL_EXPERIENCE_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Chuyên gia Đánh giá CV và Viết lách chuyên nghiệp.
Nhiệm vụ của bạn là phân tích các đoạn mô tả kinh nghiệm làm việc của ứng viên để tìm ra các điểm yếu (thiếu số liệu, chung chung) và đề xuất cách viết lại.

═══════════════════════════════════════════
NGUYÊN TẮC ĐÁNH GIÁ & ĐỀ XUẤT
═══════════════════════════════════════════
1. Tìm các câu mô tả chung chung, thiếu Metrics (số liệu đo lường).
2. Viết lại theo công thức XYZ: "Đạt được [X], bằng cách [Y], dẫn đến kết quả [Z]".
3. Dùng Action Verbs mạnh: "Xây dựng", "Tối ưu hóa", "Dẫn dắt".

### Yêu cầu JD (Để biết số năm kinh nghiệm tối thiểu):
{jd_data}

### Kinh nghiệm của ứng viên:
{cv_data}

═══════════════════════════════════════════
VÍ DỤ MẪU (FEW-SHOT EXAMPLE - TRÍCH ĐOẠN ĐẦU RA JSON)
═══════════════════════════════════════════
{{
  "experience_feedback": [
    {{
      "original_text": "Làm API cho web", "issue": "Quá chung chung, thiếu công nghệ và số liệu",
      "has_metrics": false, "impact_score": 4.0
    }}
  ],
  "rewrite_suggestions": [
    {{
      "original_text": "Làm API cho web",
      "rewritten_text": "Xây dựng hệ thống RESTful API bằng FastAPI, tối ưu hóa thời gian phản hồi giảm 20%",
      "improvement_reason": "Thêm framework sử dụng và metrics để tăng tính thuyết phục"
    }}
  ],
  "score_breakdown": [
    {{
      "category": "Kinh nghiệm làm việc", "score": 60.0, "weight": 0.25, "weighted_score": 15.0,
      "feedback": "Kinh nghiệm còn chung chung, thiếu số liệu chứng minh."
    }}
  ],
  "experience_level_match": "Ứng viên có 2 năm kinh nghiệm, đáp ứng đủ yêu cầu JD."
}}
""")


EVAL_FINAL_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Giám đốc Kỹ thuật (CTO). 
Bạn đã nhận được kết quả phân tích kỹ năng và phân tích kinh nghiệm từ các trợ lý của mình.
Nhiệm vụ của bạn là tổng hợp các kết quả đó thành một Bản Tổng hợp Đánh giá.

LƯU Ý QUAN TRỌNG: Bạn KHÔNG cần sao chép skill_analysis hay experience_feedback.
Hệ thống đã tự làm điều đó. Bạn CHỈ cần đưa ra:
1. `overall_score`: Điểm tổng (0-100)
2. `recommendation`: PASS (>=70) / CONSIDER (50-69) / REJECT (<50)
3. `score_breakdown`: CHỈ chấm điểm cho hạng mục "Học vấn & Trình bày" (20% trọng số). Các hạng mục khác đã được chấm.
4. `education_fit`: Đánh giá học vấn
5. `strengths`: Danh sách điểm mạnh (tổng hợp từ tất cả dữ liệu)
6. `weaknesses`: Danh sách điểm yếu (tổng hợp từ tất cả dữ liệu)
7. `final_conclusion`: Kết luận tổng thể

═══════════════════════════════════════════
CÔNG THỨC TÍNH ĐIỂM (TỔNG 100 ĐIỂM)
═══════════════════════════════════════════
Điểm tổng (overall_score) = Tổng các weighted_score từ:
1. Must-have Skills (40%) — Đã có từ phân tích kỹ năng
2. Nice-to-have Skills (15%) — Đã có từ phân tích kỹ năng
3. Kinh nghiệm làm việc (25%) — Đã có từ phân tích kinh nghiệm
4. Học vấn & Trình bày (20%) — BẠN chấm điểm phần này

### DỮ LIỆU ĐẦU VÀO:
- Phân tích Kỹ năng: {skill_eval}
- Phân tích Kinh nghiệm: {experience_eval}
- Học vấn & Chứng chỉ ứng viên: {education_data}

═══════════════════════════════════════════
VÍ DỤ MẪU (FEW-SHOT EXAMPLE - ĐẦU RA JSON)
═══════════════════════════════════════════
{{
  "overall_score": 78.0,
  "recommendation": "PASS",
  "score_breakdown": [
    {{
      "category": "Học vấn & Trình bày", "score": 70.0, "weight": 0.2, "weighted_score": 14.0,
      "feedback": "Cử nhân CNTT phù hợp. CV trình bày khá tốt nhưng thiếu chứng chỉ."
    }}
  ],
  "education_fit": "Cử nhân CNTT tại Bách Khoa, phù hợp với yêu cầu.",
  "strengths": ["Kinh nghiệm solid với Python và FastAPI", "Có metrics rõ ràng"],
  "weaknesses": ["Thiếu kinh nghiệm AWS", "Một số mô tả còn chung chung"],
  "final_conclusion": "Ứng viên phù hợp tốt cho vị trí Backend Developer, đáp ứng các yêu cầu cốt lõi."
}}
""")
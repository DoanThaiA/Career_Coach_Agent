from langchain_core.prompts import ChatPromptTemplate


# ──────────────────────────────────────────────
# Prompt: Bóc tách CV
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Prompt: Phân tích JD (Job Description)
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Prompt: Đánh giá Kỹ năng (Skill Matcher)
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Prompt: Tổng hợp kết quả (Final Scorer)
# ──────────────────────────────────────────────

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
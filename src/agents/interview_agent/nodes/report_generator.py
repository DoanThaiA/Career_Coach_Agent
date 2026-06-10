import json
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.prompt import REPORT_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import FinalInterviewReport
from src.core.logger import get_logger

logger = get_logger(__name__)

async def report_generator(state: InterviewState) -> dict:
    """Node tổng hợp dữ liệu và xuất báo cáo phỏng vấn chi tiết."""
    logger.info(" Bắt đầu xử lý report_generator_node ...")
    
    scores = state.get("topic_scores", {})
    reasonings = state.get("score_reasonings", {})
    
    if not scores:
        return {"final_decision": "Fail", "report": "Không có dữ liệu phỏng vấn để đánh giá."}

    # 1. Đóng gói dữ liệu đầu vào cho Prompt
    evaluation_summary = ""
    for topic, score in scores.items():
        reason = reasonings.get(topic, "Không có nhận xét.")
        evaluation_summary += f"- [Chủ đề]: {topic}\n  [Điểm]: {score}/10\n  [Chi tiết]: {reason}\n\n"

    try:
        llm = get_extraction_llm()
        prompt = REPORT_PROMPT.format(
            jd_parsed=state.get("jd_parsed", "Không có JD"),
            evaluation_summary=evaluation_summary
        ) + get_schema_instruction(FinalInterviewReport)
        
        # 2. Gọi LLM sinh báo cáo cấu trúc
        result: FinalInterviewReport = await generate_with_retry_and_correction(
            llm, prompt, FinalInterviewReport, max_retries=3
        )
        
        # 3. Render Markdown siêu chi tiết
        
        # Tạo bảng đánh giá chủ đề
        topic_table = "| Chủ đề Đánh giá | Điểm số | Nhận xét |\n"
        topic_table += "|---|:---:|---|\n"
        for t in result.topic_evaluations:
            # Xóa các ký tự ngắt dòng trong feedback để không làm vỡ bảng Markdown
            clean_feedback = t.feedback.replace("\n", " ")
            topic_table += f"| **{t.topic_name}** | {t.score}/10 | {clean_feedback} |\n"

        # Định dạng danh sách bullet points
        strengths_md = "\n".join([f"✅ {s}" for s in result.key_strengths])
        gaps_md = "\n".join([f"⚠️ {g}" for g in result.critical_gaps])
        learning_md = "\n".join([f"💡 {l}" for l in result.learning_path])

        # Phân loại màu sắc/Icon cho Quyết định
        decision_icon = "🟢" if result.final_decision == "Pass" else "🔴" if result.final_decision == "Fail" else "🟡"

        final_markdown = f"""# BÁO CÁO ĐÁNH GIÁ ỨNG VIÊN (PERFORMANCE REVIEW)

### 📊 THÔNG TIN TỔNG QUAN
- **Quyết định tuyển dụng:** {decision_icon} **{result.final_decision.upper()}**
- **Điểm đánh giá chung:** **{result.overall_score} / 10**

> **Nhận xét tổng quan:**
> {result.executive_summary}

---

### 📝 ĐÁNH GIÁ NĂNG LỰC CHI TIẾT
{topic_table}

---

### 🎯 PHÂN TÍCH CHUYÊN SÂU

**Những điểm sáng (Strengths):**
{strengths_md}

**Lỗ hổng kiến thức (Critical Gaps):**
{gaps_md}

---

### 🚀 LỘ TRÌNH CẢI THIỆN & HỌC TẬP (Actionable Advice)
Để đáp ứng tốt hơn yêu cầu công việc hoặc chuẩn bị cho các vòng tiếp theo, ứng viên nên tập trung vào:
{learning_md}
"""
        logger.info(f"✔ Đã chốt kết quả: {result.final_decision} - Điểm: {result.overall_score}")
        
        return {
            "final_decision": result.final_decision,
            "report": final_markdown
        }
        
    except Exception as e:
        logger.error(f"✖ Lỗi khi tạo báo cáo: {e}")
        return {"errors": [f"Lỗi khi tổng hợp kết quả: {str(e)}"]} 
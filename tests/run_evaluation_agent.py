
import asyncio
import json
from src.agents.evaluation_agent.graph import build_evaluation_graph
from src.core.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# Dữ liệu mẫu
# ──────────────────────────────────────────────

SAMPLE_CV = """
ĐOÀN QUỐC THÁI
Email: thai.dq@example.com | SĐT: 0901234567

HỌC VẤN:
Cử nhân CNTT, Đại học Bách Khoa (2020)

KINH NGHIỆM:
Backend Developer — Công ty ABC (01/2021 - Hiện tại)
- Xây dựng hệ thống RESTful API với FastAPI phục vụ 10,000 users/ngày
- Tối ưu truy vấn SQL giúp giảm 30% thời gian phản hồi
- Áp dụng Docker để triển khai ứng dụng

KỸ NĂNG:
Python, FastAPI, SQL, Docker
"""

SAMPLE_JD = """
VỊ TRÍ TUYỂN DỤNG: BACKEND DEVELOPER

YÊU CẦU BẮT BUỘC:
- 2+ năm kinh nghiệm phát triển với Python
- Thành thạo FastAPI
- Kinh nghiệm làm việc với SQL/PostgreSQL
- Kinh nghiệm với Docker

YÊU CẦU ƯU TIÊN:
- Có kinh nghiệm với AWS hoặc Redis

MÔ TẢ CÔNG VIỆC:
- Xây dựng API và tối ưu hóa hệ thống backend
"""


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_report(result: dict):
    """In kết quả đánh giá dạng dễ đọc."""

    # Kiểm tra lỗi
    errors = result.get("errors", [])
    if errors:
        print_section("❌ LỖI")
        for err in errors:
            print(f"  • {err}")
        return

    # CV Parsed
    cv = result.get("cv_parsed")
    if cv:
        print_section("📄 CV ĐÃ BÓC TÁCH")
        print(f"  Họ tên:    {cv.full_name or 'N/A'}")
        print(f"  Email:     {cv.email or 'N/A'}")
        print(f"  SĐT:       {cv.phone or 'N/A'}")
        print(f"  Tổng YoE:  {cv.total_yoe or 'N/A'} năm")

        if cv.education:
            print(f"\n  Học vấn ({len(cv.education)}):")
            for edu in cv.education:
                print(f"    • {edu.degree} — {edu.major} @ {edu.institution} ({edu.graduation_year})")

        if cv.work_experience:
            print(f"\n  Kinh nghiệm ({len(cv.work_experience)}):")
            for exp in cv.work_experience:
                print(f"    ▸ {exp.title} @ {exp.company} ({exp.start_date} - {exp.end_date})")
                if exp.responsibilities:
                    for r in exp.responsibilities:
                        metrics = f" → {r.metrics_or_results}" if r.metrics_or_results else " → [không có metrics]"
                        print(f"      - {r.action}{metrics}")

        if cv.skills:
            if cv.skills.technical_skills:
                tech = ", ".join(s.name for s in cv.skills.technical_skills)
                print(f"\n  Technical Skills: {tech}")
            if cv.skills.soft_skills:
                soft = ", ".join(s.name for s in cv.skills.soft_skills)
                print(f"  Soft Skills: {soft}")

        if cv.certifications:
            certs = ", ".join(f"{c.name} ({c.issue_date})" for c in cv.certifications)
            print(f"  Chứng chỉ: {certs}")

    # JD Parsed
    jd = result.get("jd_parsed")
    if jd:
        print_section("📋 JD ĐÃ PHÂN TÍCH")
        print(f"  Vị trí:     {jd.job_title}")
        print(f"  Cấp bậc:    {jd.level or 'N/A'}")
        print(f"  Min YoE:    {jd.min_years_experience or 'N/A'} năm")
        print(f"  Học vấn:    {jd.education_requirements or 'N/A'}")

        must_haves = [s for s in jd.skills if s.priority.value == "must_have"]
        nice_to_haves = [s for s in jd.skills if s.priority.value == "nice_to_have"]

        print(f"\n  Must-have ({len(must_haves)}):")
        for s in must_haves:
            yoe_str = f" ({s.min_yoe}+ năm)" if s.min_yoe else ""
            print(f"    🔴 {s.name}{yoe_str}")

        print(f"\n  Nice-to-have ({len(nice_to_haves)}):")
        for s in nice_to_haves:
            print(f"    🟢 {s.name}")

    # Evaluation Report
    report = result.get("eval_report")
    if report:
        print_section(f"⚖️  BÁO CÁO ĐÁNH GIÁ — {report.overall_score}/100 [{report.recommendation.value}]")

        # Score breakdown
        if report.score_breakdown:
            print(f"\n  📊 Chi tiết điểm:")
            print(f"  {'Hạng mục':<25} {'Điểm':>6} {'Trọng số':>10} {'Có trọng số':>12}")
            print(f"  {'-'*55}")
            for cat in report.score_breakdown:
                print(f"  {cat.category:<25} {cat.score:>5.1f} {cat.weight:>9.0%} {cat.weighted_score:>11.1f}")
                print(f"    → {cat.feedback}")

        # Skill analysis
        if report.skill_analysis:
            print(f"\n  🔍 Phân tích kỹ năng ({len(report.skill_analysis)}):")
            for s in report.skill_analysis:
                icon = "✅" if s.matched else "❌"
                priority = "🔴" if s.is_must_have else "🟢"
                equiv = f" (≈ {s.equivalent_skill})" if s.equivalent_skill else ""
                evidence = f" — {s.cv_evidence}" if s.cv_evidence else ""
                print(f"    {icon} {priority} {s.skill_name} [{s.score}/10]{equiv}{evidence}")
                if s.note:
                    print(f"       📝 {s.note}")

        # Experience feedback
        if report.experience_feedback:
            print(f"\n  💼 Nhận xét kinh nghiệm ({len(report.experience_feedback)}):")
            for fb in report.experience_feedback:
                metrics_icon = "📊" if fb.has_metrics else "⚠️"
                company = f"[{fb.company}] " if fb.company else ""
                print(f"    {metrics_icon} {company}Impact: {fb.impact_score}/10")
                print(f"       Gốc:  \"{fb.original_text}\"")
                print(f"       Vấn đề: {fb.issue}")

        # Rewrite suggestions
        if report.rewrite_suggestions:
            print(f"\n  ✏️  Đề xuất viết lại ({len(report.rewrite_suggestions)}):")
            for rw in report.rewrite_suggestions:
                print(f"    ❌ Gốc:     \"{rw.original_text}\"")
                print(f"    ✅ Viết lại: \"{rw.rewritten_text}\"")
                print(f"       Lý do:   {rw.improvement_reason}")
                print()

        # Strengths & Weaknesses
        if report.strengths:
            print(f"\n  💪 Điểm mạnh:")
            for s in report.strengths:
                print(f"    + {s}")

        if report.weaknesses:
            print(f"\n  ⚡ Điểm yếu:")
            for w in report.weaknesses:
                print(f"    - {w}")

        # Education & Experience match
        if report.education_fit:
            print(f"\n  🎓 Học vấn: {report.education_fit}")
        if report.experience_level_match:
            print(f"  📅 Kinh nghiệm: {report.experience_level_match}")

        # Conclusion
        print(f"\n  📝 Kết luận:")
        print(f"     {report.final_conclusion}")

        # Raw JSON (để debug)
        print_section("📦 RAW JSON OUTPUT")
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False, default=str))


async def main():
    print("🚀 Bắt đầu chạy Evaluation Agent ...")
    print(f"   CV: {len(SAMPLE_CV)} ký tự")
    print(f"   JD: {len(SAMPLE_JD)} ký tự")

    # Build graph mới (không dùng singleton để tránh cache)
    graph = build_evaluation_graph()

    # Chạy full pipeline
    result = await graph.ainvoke({
        "cv_content": SAMPLE_CV,
        "job_requirement": SAMPLE_JD,
        "errors": [],
    })

    # In kết quả
    print_report(result)

    print(f"\n{'='*60}")
    print(f"  ✅ HOÀN TẤT")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())

"""Script chạy evaluation agent với dữ liệu mẫu để rà soát kết quả.

Cách chạy:
    python -m tests.run_evaluation_agent

Yêu cầu:
    - LLM server đang chạy tại LLM_BASE_URL (xem .env)
    - Đã cài đủ dependencies (uv sync)
"""

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
LinkedIn: linkedin.com/in/thaidq

============================================
HỌC VẤN
============================================
Cử nhân Công nghệ Thông tin
Đại học Bách Khoa TP.HCM — Tốt nghiệp 2020
GPA: 7.8/10

============================================
KINH NGHIỆM LÀM VIỆC
============================================

Senior Backend Developer — Công ty XYZ Tech (07/2023 - Hiện tại)
- Dẫn dắt team 5 người phát triển hệ thống microservices xử lý 50,000 requests/giây
- Thiết kế và triển khai CI/CD pipeline với GitHub Actions, giảm 60% thời gian deploy
- Tối ưu hóa kiến trúc hệ thống, giảm chi phí AWS hàng tháng 25% (~$3,000/tháng)
- Xây dựng hệ thống monitoring với Prometheus + Grafana

Backend Developer — Công ty ABC Solutions (01/2021 - 06/2023)
- Xây dựng RESTful API với FastAPI phục vụ 10,000 users/ngày
- Tối ưu hóa truy vấn SQL phức tạp, giảm 30% thời gian tải trang
- Phát triển tính năng mới cho hệ thống e-commerce
- Tham gia vào quá trình review code và mentor junior developers
- Viết unit test và integration test cho các module chính

Intern — Công ty DEF (06/2020 - 12/2020)
- Hỗ trợ team phát triển dashboard admin bằng ReactJS
- Tìm hiểu và áp dụng Docker cho môi trường development

============================================
KỸ NĂNG
============================================
Ngôn ngữ lập trình: Python (5 năm), JavaScript (3 năm), SQL
Framework: FastAPI, Django, ReactJS, NextJS
Database: PostgreSQL, MongoDB, Redis
DevOps: Docker, Kubernetes, AWS (EC2, S3, RDS, Lambda), GitHub Actions
Tools: Git, Jira, Confluence, Grafana, Prometheus
Kỹ năng mềm: Leadership, Problem Solving, Communication

============================================
CHỨNG CHỈ
============================================
- AWS Solutions Architect Associate — Amazon (2024)
- IELTS 7.0 (2022)

============================================
DỰ ÁN TIÊU BIỂU
============================================

Hệ thống E-commerce Platform (2023-2024)
- Vai trò: Tech Lead
- Mô tả: Thiết kế kiến trúc microservices cho nền tảng thương mại điện tử phục vụ 100K+ users
- Công nghệ: Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, AWS
- Kết quả: Hệ thống xử lý 1,000+ đơn hàng/giờ, uptime 99.9%

Real-time Chat System (2022)
- Vai trò: Backend Developer
- Mô tả: Xây dựng hệ thống chat real-time sử dụng WebSocket
- Công nghệ: Python, FastAPI, Redis, WebSocket
"""

SAMPLE_JD = """
VỊ TRÍ TUYỂN DỤNG: SENIOR BACKEND DEVELOPER

THÔNG TIN CHUNG:
- Mức lương: 25-40 triệu VNĐ
- Kinh nghiệm: 3+ năm
- Hình thức: Full-time, On-site (TP.HCM)

YÊU CẦU BẮT BUỘC:
- Tối thiểu 3 năm kinh nghiệm phát triển Backend với Python
- Thành thạo FastAPI hoặc Django
- Kinh nghiệm làm việc với PostgreSQL hoặc MySQL
- Hiểu biết sâu về RESTful API design
- Kinh nghiệm với Docker và containerization
- Kinh nghiệm với Kubernetes (K8s) để orchestration
- Có khả năng thiết kế hệ thống (System Design)
- Tiếng Anh đọc hiểu tài liệu kỹ thuật

YÊU CẦU ƯU TIÊN:
- Kinh nghiệm với AWS (EC2, S3, RDS, Lambda)
- Hiểu biết về Microservices Architecture
- Kinh nghiệm với Message Queue (RabbitMQ, Kafka)
- Kinh nghiệm với Redis
- Có kinh nghiệm CI/CD pipeline
- Kinh nghiệm mentoring junior developers

YÊU CẦU HỌC VẤN:
- Cử nhân Công nghệ Thông tin, Khoa học Máy tính hoặc tương đương

MÔ TẢ CÔNG VIỆC:
- Thiết kế và phát triển các hệ thống backend có khả năng mở rộng
- Code review và đảm bảo chất lượng code
- Tham gia vào quá trình thiết kế kiến trúc hệ thống
- Mentoring và hỗ trợ junior developers
- Viết technical documentation
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

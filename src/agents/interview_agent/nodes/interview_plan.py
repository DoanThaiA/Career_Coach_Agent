import json
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.interview_agent.prompt import INTERVIEW_PLANNER_PROMPT
from src.agents.interview_agent.state import InterviewState
from src.agents.interview_agent.output_schema import InterviewPlan
from src.core.logger import get_logger
from langchain_core.runnables.config import RunnableConfig

logger = get_logger(__name__)


def _build_slim_cv(cv_parsed) -> str:
    """Tạo bản CV thu gọn chỉ chứa các thông tin cần thiết cho interview planning & scoring.
    Giảm 60-70% token so với full JSON dump."""
    data = {
        "name": cv_parsed.full_name,
        "title": cv_parsed.summary.professional_title if cv_parsed.summary else None,
        "total_yoe": cv_parsed.total_yoe,
        "skills": [s.name for s in (cv_parsed.skills.technical_skills if cv_parsed.skills else [])],
        "work_experience": [
            {
                "company": w.company,
                "title": w.job_title,
                "period": f"{w.start_date} - {w.end_date}",
                "highlights": w.achievements[:3] if w.achievements else w.responsibilities[:2],
                "tech": w.technologies_used[:8],
            }
            for w in cv_parsed.work_experience
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree, "major": e.major}
            for e in cv_parsed.education
        ],
        "projects": [
            {"name": p.name, "tech": p.technologies[:5], "role": p.role}
            for p in cv_parsed.projects[:3]
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=None)


def _build_slim_jd(jd_parsed) -> str:
    """Tạo bản JD thu gọn chỉ chứa các thông tin cần thiết."""
    skills = jd_parsed.skills if jd_parsed.skills else None
    data = {
        "title": jd_parsed.job_title,
        "level": jd_parsed.level,
        "min_yoe": jd_parsed.min_years_experience,
        "must_have_skills": [s.name for s in (skills.required_technical_skills if skills else []) if s.weight == "must_have"],
        "important_skills": [s.name for s in (skills.required_technical_skills if skills else []) if s.weight == "important"],
        "preferred_skills": [s.name for s in (skills.preferred_technical_skills if skills else [])],
        "soft_skills": skills.required_soft_skills[:5] if skills else [],
        "responsibilities": jd_parsed.responsibilities[:8],
        "qualifications": jd_parsed.qualifications.must_have[:5] if jd_parsed.qualifications else [],
    }
    return json.dumps(data, ensure_ascii=False, indent=None)


async def interview_plan(state: InterviewState, config: RunnableConfig) -> dict:
    """Node tạo đề cương phỏng vấn và cache slim CV/JD texts."""
    logger.info("▶ Bắt đầu xử lý interview_plan_node ...")
    jd_parsed = state.get("jd_parsed")
    cv_parsed = state.get("cv_parsed")

    if not jd_parsed:
        return {"errors": ["Không tìm thấy nội dung JD (job_requirement)"]}

    if not cv_parsed:
        return {"errors": ["Không tìm thấy nội dung CV"]}

    # Build slim texts một lần và cache vào state
    slim_cv = _build_slim_cv(cv_parsed)
    slim_jd = _build_slim_jd(jd_parsed)

    try:
        llm = get_extraction_llm()

        prompt = INTERVIEW_PLANNER_PROMPT.format(
            cv_context=slim_cv,
            jd_context=slim_jd,
        ) + get_schema_instruction(InterviewPlan)

        result = await generate_with_retry_and_correction(
            llm, prompt, InterviewPlan, max_retries=3, config=config
        )

        if not result or not result.topics:
            return {"errors": ["Không thể tạo danh sách chủ đề phỏng vấn từ dữ liệu đầu vào."]}

        topics = [topic.model_dump() for topic in result.topics]

        logger.info(f"✔ Tạo đề cương phỏng vấn thành công với {len(topics)} chủ đề")
        return {
            "topics": topics,
            "current_topic_index": 0,
            "followup_count": 0,
            "followup_count_per_topic": {},
            "slim_cv_text": slim_cv,
            "slim_jd_text": slim_jd,
        }
    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý interview_plan_node: {e}")
        return {"errors": [f"Lỗi tạo đề cương phỏng vấn: {str(e)}"]}
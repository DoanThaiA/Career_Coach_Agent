from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import FeedbackAssessment
from src.agents.evaluation_agent.prompt import GENERATE_FEEDBACK_PROMPT
from src.utils import get_evaluation_llm, generate_with_retry_and_correction, get_schema_instruction
from langchain_core.runnables.config import RunnableConfig

async def generate_feedback_node(state: EvaluationState, config: RunnableConfig) -> dict:
    cv, jd = state.get("cv_parsed"), state.get("jd_parsed")
    llm = get_evaluation_llm()

    if cv.work_experience:
        cv_exp_lines = []
        for w in cv.work_experience:
            achievements_str = ", ".join(w.achievements) if isinstance(w.achievements, list) else (w.achievements or "")
            cv_exp_lines.append(f"- **{w.job_title}** tại **{w.company}**: {achievements_str}")
        cv_experience_str = "\n".join(cv_exp_lines)
    else:
        cv_experience_str = "Không có kinh nghiệm làm việc"

    if jd.responsibilities:
        jd_resp_str = "\n".join([f"- {r}" for r in jd.responsibilities])
    else:
        jd_resp_str = "Không có yêu cầu công việc cụ thể"

    prompt_text = GENERATE_FEEDBACK_PROMPT.format(
        job_title=jd.job_title,
        matched_skills=state.get('matched_skills', []),
        missing_skills=state.get('missing_skills', []),
        missing_must_have_skills=state.get('missing_must_have_skills', []),
        experience_score=state.get('experience_score', 0),
        min_years_experience=jd.min_years_experience or 0,
        cv_total_yoe=cv.total_yoe or 0,
        education_score=state.get('education_score', 0),
        cv_experience=cv_experience_str,
        jd_responsibilities=jd_resp_str
    )

    full_prompt = prompt_text + get_schema_instruction(FeedbackAssessment)
    result: FeedbackAssessment = await generate_with_retry_and_correction(
        llm, full_prompt, FeedbackAssessment, max_retries=3, config=config
    )

    return {
        "qualitative_score": result.qualitative_score,
        "overall_impression": result.overall_impression,
        "strengths": result.strengths,
        "improvement_suggestions": [s.model_dump() for s in result.improvement_suggestions],
    }

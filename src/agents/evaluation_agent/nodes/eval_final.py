import json
from src.core.logger import get_logger
from src.utils import get_evaluation_llm, generate_with_retry_and_correction, get_schema_instruction
from src.agents.evaluation_agent.prompt import EVAL_FINAL_PROMPT
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.output_schema import (
    EvaluationReport,
    FinalSynthesis,
    Recommendation,
    CategoryScore,
    SkillEvaluationResult,
    ExperienceEvaluationResult,
)

logger = get_logger(__name__)



def compute_deterministic_score(
    skill_eval: SkillEvaluationResult,
    experience_eval: ExperienceEvaluationResult,
    synthesis: FinalSynthesis,
) -> float:
    """Tính overall_score deterministic từ các thành phần.
    
    Công thức:
    - Skill score (55%): lấy từ weighted_score trong skill_eval.score_breakdown
    - Experience score (25%): lấy từ weighted_score trong experience_eval.score_breakdown
    - Education + Trình bày (20%): lấy từ LLM synthesis.score_breakdown
    
    Nếu LLM đã tính tổng hợp lý, ta ưu tiên dùng dữ liệu từ các node trước.
    """
    total = 0.0
    
    # Skill scores (từ eval_skills - đáng tin hơn vì chuyên biệt)
    for cat in skill_eval.score_breakdown:
        total += cat.weighted_score
    
    for cat in experience_eval.score_breakdown:
        total += cat.weighted_score
    
    for cat in synthesis.score_breakdown:
        total += cat.weighted_score
    
    return round(max(0.0, min(100.0, total)), 1)


def determine_recommendation(score: float) -> Recommendation:
    """Xác định recommendation từ score (deterministic)."""
    if score >= 70:
        return Recommendation.PASS
    elif score >= 50:
        return Recommendation.CONSIDER
    else:
        return Recommendation.REJECT


def validate_report(report: EvaluationReport) -> EvaluationReport:
    """Đảm bảo tính nhất quán của báo cáo (backward-compatible)."""
    report.recommendation = determine_recommendation(report.overall_score)
    return report

async def eval_final_node(state: EvaluationState) -> dict:
    """Node tổng hợp đánh giá và tạo báo cáo cuối cùng.
    
    Tối ưu: LLM chỉ sinh FinalSynthesis (gọn nhẹ), sau đó Python
    sẽ tự copy skill_analysis, experience_feedback từ state và
    tính điểm deterministic.
    """
    logger.info("▶ Bắt đầu xử lý eval_final_node ...")
    
    cv_parsed = state.get("cv_parsed")
    jd_parsed = state.get("jd_parsed")
    skill_eval = state.get("skill_evaluation")
    experience_eval = state.get("experience_evaluation")
    
    if not cv_parsed or not jd_parsed or not skill_eval or not experience_eval:
        return {"errors": ["Thiếu dữ liệu trung gian để tạo báo cáo tổng hợp."]}
        
    try:
        llm = get_evaluation_llm()
        
        education_data = {
            "education": [edu.model_dump() for edu in (cv_parsed.education or [])],
            "certifications": [cert.model_dump() for cert in (cv_parsed.certifications or [])],
            "education_requirements": jd_parsed.education_requirements,
        }
        
        prompt = EVAL_FINAL_PROMPT.format(
            skill_eval=skill_eval.model_dump_json(indent=2),
            experience_eval=experience_eval.model_dump_json(indent=2),
            education_data=json.dumps(education_data, indent=2, ensure_ascii=False),
        ) + get_schema_instruction(FinalSynthesis)
        
        synthesis = await generate_with_retry_and_correction(
            llm, prompt, FinalSynthesis, max_retries=3
        )
        
        deterministic_score = compute_deterministic_score(
            skill_eval, experience_eval, synthesis
        )
        recommendation = determine_recommendation(deterministic_score)
        
        # Gộp score_breakdown từ cả 3 nguồn
        all_score_breakdown = (
            list(skill_eval.score_breakdown) +
            list(experience_eval.score_breakdown) +
            list(synthesis.score_breakdown)
        )
        
        eval_report = EvaluationReport(
            overall_score=deterministic_score,
            recommendation=recommendation,
            score_breakdown=all_score_breakdown,
            skill_analysis=skill_eval.skill_analysis,
            experience_feedback=experience_eval.experience_feedback,
            rewrite_suggestions=experience_eval.rewrite_suggestions,
            experience_level_match=experience_eval.experience_level_match,
            education_fit=synthesis.education_fit,
            strengths=synthesis.strengths,
            weaknesses=synthesis.weaknesses,
            final_conclusion=synthesis.final_conclusion,
        )
        
        logger.info(
            f"✔ Đánh giá hoàn tất. Score: {eval_report.overall_score} "
            f"(LLM: {synthesis.overall_score}) - {eval_report.recommendation.value}"
        )
        return {"eval_report": eval_report}
    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý eval_final_node: {e}", exc_info=True)
        return {"errors": [f"Lỗi tổng hợp đánh giá: {str(e)}"]}

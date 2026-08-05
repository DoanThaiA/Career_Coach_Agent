"""Tests cho evaluation_agent module.

Bao gồm:
- Unit tests cho output schemas
- Unit tests cho validate_report
- Unit tests cho routing functions
- Unit tests cho parse_llm_json
- Unit tests cho từng node (mock LLM)
- Integration test cho full graph (mock LLM)
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.evaluation_agent.output_schema import (
    EvaluationReport,
    FinalSynthesis,
    Recommendation,
    SkillMatch,
    ExperienceFeedback,
    RewriteSuggestion,
    CategoryScore,
    SkillEvaluationResult,
    ExperienceEvaluationResult,
)
from src.services.parse_cv import (
    CVInformation,
    Education,
    ExtractedSkill,
    Skill,
    WorkExperience,
    ResponsibilityDetail,
    Project,
    Certification,
)
from src.services.parse_jd import (
    JDRequirements,
    JDSkill,
    SkillPriority,
)
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.nodes.eval_final import validate_report, compute_deterministic_score, determine_recommendation
from src.agents.evaluation_agent.graph import check_eval_readiness, should_finalize
from src.utils import parse_llm_json


# ──────────────────────────────────────────────
# Fixtures: Mock data dùng chung
# ──────────────────────────────────────────────

@pytest.fixture
def sample_cv_text():
    return """
    ĐOÀN QUỐC THÁI
    Email: thai.dq@example.com | SĐT: 0901234567
    Backend Developer - Công ty ABC (01/2021 - 06/2023)
    - Xây dựng hệ thống API với FastAPI phục vụ 10,000 users/ngày
    KỸ NĂNG: Python, FastAPI, PostgreSQL
    """


@pytest.fixture
def sample_jd_text():
    return """
    Vị trí: Senior Backend Developer
    Yêu cầu bắt buộc: Python, FastAPI, PostgreSQL
    Ưu tiên: AWS, Redis
    """


@pytest.fixture
def sample_cv_parsed():
    return CVInformation(
        full_name="Đoàn Quốc Thái",
        email="thai.dq@example.com",
        phone="0901234567",
        total_yoe=5.5,
        education=[
            Education(degree="Cử nhân", major="CNTT", institution="Bách Khoa", graduation_year="2020")
        ],
        work_experience=[
            WorkExperience(
                title="Backend Developer", company="ABC",
                start_date="01/2021", end_date="06/2023",
                responsibilities=[
                    ResponsibilityDetail(action="Xây dựng API", metrics_or_results="10,000 users/ngày"),
                    ResponsibilityDetail(action="Phát triển tính năng mới", metrics_or_results=None),
                ],
            ),
        ],
        skills=Skill(
            technical_skills=[
                ExtractedSkill(name="Python", context="Backend", yoe=5.5),
                ExtractedSkill(name="FastAPI", context="REST API", yoe=2.5),
            ],
        ),
    )


@pytest.fixture
def sample_jd_parsed():
    return JDRequirements(
        job_title="Senior Backend Developer",
        level="Senior",
        min_years_experience=3.0,
        skills=[
            JDSkill(name="Python", priority=SkillPriority.MUST_HAVE, min_yoe=3.0),
            JDSkill(name="FastAPI", priority=SkillPriority.MUST_HAVE),
            JDSkill(name="AWS", priority=SkillPriority.NICE_TO_HAVE),
        ],
    )

@pytest.fixture
def sample_skill_eval():
    return SkillEvaluationResult(
        skill_analysis=[
            SkillMatch(skill_name="Python", matched=True, is_must_have=True, score=10.0, cv_evidence="5.5 năm"),
        ],
        score_breakdown=[
            CategoryScore(category="Must-have Skills", score=85.0, weight=0.4, weighted_score=34.0, feedback="OK"),
        ]
    )

@pytest.fixture
def sample_experience_eval():
    return ExperienceEvaluationResult(
        experience_feedback=[
            ExperienceFeedback(original_text="Phát triển tính năng", issue="Chung chung", has_metrics=False, impact_score=3.0),
        ],
        rewrite_suggestions=[
            RewriteSuggestion(original_text="Phát triển tính năng", rewritten_text="Xây dựng 5 tính năng mới", improvement_reason="Thêm số liệu"),
        ],
        score_breakdown=[
            CategoryScore(category="Kinh nghiệm", score=60.0, weight=0.25, weighted_score=15.0, feedback="OK"),
        ],
        experience_level_match="Phù hợp",
    )

@pytest.fixture
def sample_synthesis():
    """FinalSynthesis mà LLM sẽ sinh (gọn nhẹ, không chứa skill/experience data)."""
    return FinalSynthesis(
        overall_score=78.0,
        recommendation=Recommendation.PASS,
        score_breakdown=[
            CategoryScore(category="Học vấn & Trình bày", score=70.0, weight=0.2, weighted_score=14.0, feedback="OK"),
        ],
        education_fit="Phù hợp",
        strengths=["Python solid"],
        weaknesses=["Thiếu metrics"],
        final_conclusion="Phù hợp tốt.",
    )

@pytest.fixture
def sample_eval_report():
    return EvaluationReport(
        overall_score=63.0,
        recommendation=Recommendation.CONSIDER,
        score_breakdown=[
            CategoryScore(category="Must-have Skills", score=85.0, weight=0.4, weighted_score=34.0, feedback="OK"),
            CategoryScore(category="Kinh nghiệm", score=60.0, weight=0.25, weighted_score=15.0, feedback="OK"),
            CategoryScore(category="Học vấn & Trình bày", score=70.0, weight=0.2, weighted_score=14.0, feedback="OK"),
        ],
        skill_analysis=[
            SkillMatch(skill_name="Python", matched=True, is_must_have=True, score=10.0, cv_evidence="5.5 năm"),
        ],
        experience_feedback=[
            ExperienceFeedback(original_text="Phát triển tính năng", issue="Chung chung", has_metrics=False, impact_score=3.0),
        ],
        rewrite_suggestions=[
            RewriteSuggestion(original_text="Phát triển tính năng", rewritten_text="Xây dựng 5 tính năng mới", improvement_reason="Thêm số liệu"),
        ],
        strengths=["Python solid"],
        weaknesses=["Thiếu metrics"],
        final_conclusion="Phù hợp tốt.",
    )


def _make_mock_llm_response(content: str):
    """Tạo mock LLM response object."""
    mock_response = MagicMock()
    mock_response.content = content
    return mock_response


# ──────────────────────────────────────────────
# Test 1: Output Schemas
# ──────────────────────────────────────────────

class TestOutputSchemas:
    def test_cv_information_valid(self, sample_cv_parsed):
        assert sample_cv_parsed.full_name == "Đoàn Quốc Thái"
        assert sample_cv_parsed.total_yoe == 5.5

    def test_jd_requirements_valid(self, sample_jd_parsed):
        must_haves = [s for s in sample_jd_parsed.skills if s.priority == SkillPriority.MUST_HAVE]
        assert len(must_haves) == 2

    def test_evaluation_report_score_constraint(self):
        with pytest.raises(Exception):
            EvaluationReport(
                overall_score=150.0, recommendation=Recommendation.PASS,
                score_breakdown=[], skill_analysis=[], experience_feedback=[],
                rewrite_suggestions=[], strengths=[], weaknesses=[], final_conclusion="Test",
            )

    def test_recommendation_enum(self):
        assert Recommendation.PASS.value == "PASS"


# ──────────────────────────────────────────────
# Test 2: parse_llm_json (robust JSON parser)
# ──────────────────────────────────────────────

class TestParseLlmJson:
    """Test hàm parse_llm_json trong utils.py."""

    def test_pure_json(self, sample_cv_parsed):
        json_str = sample_cv_parsed.model_dump_json()
        result = parse_llm_json(json_str, CVInformation)
        assert result.full_name == "Đoàn Quốc Thái"


# ──────────────────────────────────────────────
# Test 3: validate_report
# ──────────────────────────────────────────────

class TestValidateReport:
    def _make_report(self, score, recommendation):
        return EvaluationReport(
            overall_score=score, recommendation=recommendation,
            score_breakdown=[], skill_analysis=[], experience_feedback=[],
            rewrite_suggestions=[], strengths=["test"], weaknesses=["test"],
            final_conclusion="Test",
        )

    def test_pass_correct(self):
        r = validate_report(self._make_report(85.0, Recommendation.PASS))
        assert r.recommendation == Recommendation.PASS

    def test_fix_pass_to_reject(self):
        r = validate_report(self._make_report(30.0, Recommendation.PASS))
        assert r.recommendation == Recommendation.REJECT


class TestDeterministicScoring:
    """Test tính điểm deterministic (bằng Python, không qua LLM)."""

    def test_compute_score(self, sample_skill_eval, sample_experience_eval, sample_synthesis):
        score = compute_deterministic_score(sample_skill_eval, sample_experience_eval, sample_synthesis)
        # 34.0 (skill) + 15.0 (experience) + 14.0 (education) = 63.0
        assert score == 63.0

    def test_determine_recommendation_pass(self):
        assert determine_recommendation(70.0) == Recommendation.PASS

    def test_determine_recommendation_consider(self):
        assert determine_recommendation(55.0) == Recommendation.CONSIDER

    def test_determine_recommendation_reject(self):
        assert determine_recommendation(30.0) == Recommendation.REJECT

    def test_boundary_70(self):
        assert determine_recommendation(70.0) == Recommendation.PASS

    def test_boundary_50(self):
        assert determine_recommendation(50.0) == Recommendation.CONSIDER

    def test_boundary_49_9(self):
        assert determine_recommendation(49.9) == Recommendation.REJECT


# ──────────────────────────────────────────────
# Test 4: Routing functions
# ──────────────────────────────────────────────

class TestRoutingFunctions:
    def test_validate_input_success(self, sample_cv_parsed, sample_jd_parsed):
        state = {"cv_parsed": sample_cv_parsed, "jd_parsed": sample_jd_parsed, "errors": []}
        from src.agents.evaluation_agent.graph import validate_input
        assert validate_input(state) == "start_evaluate"
        
    def test_validate_input_failure_no_cv(self, sample_jd_parsed):
        state = {"jd_parsed": sample_jd_parsed, "errors": []}
        from src.agents.evaluation_agent.graph import validate_input
        assert validate_input(state) == "end"





# ──────────────────────────────────────────────
# Test 6: eval nodes (mock LLM)
# ──────────────────────────────────────────────

class TestEvalNodes:
    @pytest.mark.asyncio
    async def test_eval_skills(self, sample_cv_parsed, sample_jd_parsed, sample_skill_eval):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = _make_mock_llm_response(sample_skill_eval.model_dump_json())
        with patch("src.agents.evaluation_agent.nodes.eval_skills.get_evaluation_llm", return_value=mock_llm):
            from src.agents.evaluation_agent.nodes.eval_skills import eval_skills_node
            result = await eval_skills_node({"cv_parsed": sample_cv_parsed, "jd_parsed": sample_jd_parsed, "errors": []})
            assert "skill_evaluation" in result

    @pytest.mark.asyncio
    async def test_eval_experience(self, sample_cv_parsed, sample_jd_parsed, sample_experience_eval):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = _make_mock_llm_response(sample_experience_eval.model_dump_json())
        with patch("src.agents.evaluation_agent.nodes.eval_experience.get_evaluation_llm", return_value=mock_llm):
            from src.agents.evaluation_agent.nodes.eval_experience import eval_experience_node
            result = await eval_experience_node({"cv_parsed": sample_cv_parsed, "jd_parsed": sample_jd_parsed, "errors": []})
            assert "experience_evaluation" in result

    @pytest.mark.asyncio
    async def test_eval_final(self, sample_cv_parsed, sample_jd_parsed, sample_skill_eval, sample_experience_eval, sample_synthesis):
        """eval_final now uses FinalSynthesis (lightweight) and assembles the report in Python."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = _make_mock_llm_response(sample_synthesis.model_dump_json())
        with patch("src.agents.evaluation_agent.nodes.eval_final.get_evaluation_llm", return_value=mock_llm):
            from src.agents.evaluation_agent.nodes.eval_final import eval_final_node
            result = await eval_final_node({
                "cv_parsed": sample_cv_parsed, 
                "jd_parsed": sample_jd_parsed, 
                "skill_evaluation": sample_skill_eval,
                "experience_evaluation": sample_experience_eval,
                "errors": []
            })
            assert "eval_report" in result
            report = result["eval_report"]
            # Kiểm tra data được copy từ Python, không qua LLM
            assert len(report.skill_analysis) == len(sample_skill_eval.skill_analysis)
            assert len(report.experience_feedback) == len(sample_experience_eval.experience_feedback)
            # Kiểm tra deterministic score
            assert report.overall_score == 63.0  # 34 + 15 + 14


# ──────────────────────────────────────────────
# Test 7: Integration — Full Graph (mock LLM)
# ──────────────────────────────────────────────

class TestFullGraph:
    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, sample_cv_text, sample_jd_text,
        sample_cv_parsed, sample_jd_parsed, 
        sample_skill_eval, sample_experience_eval, sample_synthesis,
    ):
        mock_skill_llm = AsyncMock()
        mock_skill_llm.ainvoke.return_value = _make_mock_llm_response(sample_skill_eval.model_dump_json())

        mock_exp_llm = AsyncMock()
        mock_exp_llm.ainvoke.return_value = _make_mock_llm_response(sample_experience_eval.model_dump_json())

        mock_final_llm = AsyncMock()
        mock_final_llm.ainvoke.return_value = _make_mock_llm_response(sample_synthesis.model_dump_json())

        with patch("src.agents.evaluation_agent.nodes.eval_skills.get_evaluation_llm", return_value=mock_skill_llm), \
             patch("src.agents.evaluation_agent.nodes.eval_experience.get_evaluation_llm", return_value=mock_exp_llm), \
             patch("src.agents.evaluation_agent.nodes.eval_final.get_evaluation_llm", return_value=mock_final_llm):

            from src.agents.evaluation_agent.graph import build_evaluation_graph
            graph = build_evaluation_graph()
            result = await graph.ainvoke({
                "cv_parsed": sample_cv_parsed,
                "jd_parsed": sample_jd_parsed,
                "errors": [],
            })

            assert result.get("cv_parsed") is not None
            assert result.get("jd_parsed") is not None
            assert result.get("skill_evaluation") is not None
            assert result.get("experience_evaluation") is not None
            assert result.get("eval_report") is not None
            assert result["eval_report"].overall_score == 63.0


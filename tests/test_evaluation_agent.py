"""Tests cho evaluation_agent module.

Bao gồm:
- Unit tests cho từng node (mock LLM)
- Unit tests cho validate_report
- Unit tests cho routing functions
- Unit tests cho output schemas
- Integration test cho full graph (mock LLM)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.evaluation_agent.output_schema import (
    CVInformation,
    Education,
    ExtractedSkill,
    Skill,
    WorkExperience,
    ResponsibilityDetail,
    Project,
    Certification,
    JDRequirements,
    JDSkill,
    SkillPriority,
    EvaluationReport,
    Recommendation,
    SkillMatch,
    ExperienceFeedback,
    RewriteSuggestion,
    CategoryScore,
)
from src.agents.evaluation_agent.state import EvaluationState
from src.agents.evaluation_agent.nodes.eval import validate_report
from src.agents.evaluation_agent.graph import (
    check_readiness,
    should_evaluate,
)


# ──────────────────────────────────────────────
# Fixtures: Mock data dùng chung
# ──────────────────────────────────────────────

@pytest.fixture
def sample_cv_text():
    return """
    ĐOÀN QUỐC THÁI
    Email: thai.dq@example.com | SĐT: 0901234567

    HỌC VẤN:
    - Cử nhân Công nghệ Thông tin, Đại học Bách Khoa TP.HCM, 2020
    
    KINH NGHIỆM LÀM VIỆC:
    Backend Developer - Công ty ABC (01/2021 - 06/2023)
    - Xây dựng hệ thống API với FastAPI phục vụ 10,000 users/ngày
    - Tối ưu hóa truy vấn SQL giúp giảm 30% thời gian tải trang
    - Phát triển tính năng mới cho hệ thống

    Senior Developer - Công ty XYZ (07/2023 - Hiện tại)
    - Dẫn dắt team 5 người phát triển microservices
    - Triển khai CI/CD pipeline với GitHub Actions

    KỸ NĂNG:
    - Python, FastAPI, Django, PostgreSQL, Redis
    - Docker, Kubernetes, AWS
    - Git, CI/CD
    """


@pytest.fixture
def sample_jd_text():
    return """
    Vị trí: Senior Backend Developer
    
    Yêu cầu bắt buộc:
    - 3+ năm kinh nghiệm với Python
    - Thành thạo FastAPI hoặc Django
    - Kinh nghiệm với PostgreSQL
    - Kinh nghiệm với Docker và Kubernetes
    
    Ưu tiên:
    - Kinh nghiệm với AWS
    - Hiểu biết về Microservices architecture
    - Kinh nghiệm với Redis/Kafka
    
    Yêu cầu học vấn: Cử nhân CNTT hoặc tương đương
    """


@pytest.fixture
def sample_cv_parsed():
    return CVInformation(
        full_name="Đoàn Quốc Thái",
        email="thai.dq@example.com",
        phone="0901234567",
        total_yoe=5.5,
        education=[
            Education(
                degree="Cử nhân",
                major="Công nghệ Thông tin",
                institution="Đại học Bách Khoa TP.HCM",
                graduation_year="2020",
            )
        ],
        work_experience=[
            WorkExperience(
                title="Backend Developer",
                company="Công ty ABC",
                start_date="01/2021",
                end_date="06/2023",
                responsibilities=[
                    ResponsibilityDetail(
                        action="Xây dựng hệ thống API với FastAPI",
                        metrics_or_results="Phục vụ 10,000 users/ngày",
                    ),
                    ResponsibilityDetail(
                        action="Tối ưu hóa truy vấn SQL",
                        metrics_or_results="Giảm 30% thời gian tải trang",
                    ),
                    ResponsibilityDetail(
                        action="Phát triển tính năng mới cho hệ thống",
                        metrics_or_results=None,
                    ),
                ],
            ),
            WorkExperience(
                title="Senior Developer",
                company="Công ty XYZ",
                start_date="07/2023",
                end_date="Hiện tại",
                responsibilities=[
                    ResponsibilityDetail(
                        action="Dẫn dắt team 5 người phát triển microservices",
                        metrics_or_results=None,
                    ),
                    ResponsibilityDetail(
                        action="Triển khai CI/CD pipeline với GitHub Actions",
                        metrics_or_results=None,
                    ),
                ],
            ),
        ],
        skills=Skill(
            technical_skills=[
                ExtractedSkill(name="Python", context="Viết API backend", yoe=5.5),
                ExtractedSkill(name="FastAPI", context="Xây dựng REST API", yoe=2.5),
                ExtractedSkill(name="Django", context=None, yoe=None),
                ExtractedSkill(name="PostgreSQL", context="Database chính", yoe=5.0),
                ExtractedSkill(name="Redis", context="Caching", yoe=None),
                ExtractedSkill(name="Docker", context="Containerization", yoe=3.0),
                ExtractedSkill(name="Kubernetes", context="Orchestration", yoe=3.0),
                ExtractedSkill(name="AWS", context="Cloud infrastructure", yoe=None),
            ],
            soft_skills=[
                ExtractedSkill(name="Leadership", context="Dẫn dắt team 5 người"),
            ],
        ),
        certifications=[
            Certification(name="AWS Solutions Architect", issuer="Amazon", issue_date="2024"),
        ],
    )


@pytest.fixture
def sample_jd_parsed():
    return JDRequirements(
        job_title="Senior Backend Developer",
        level="Senior",
        min_years_experience=3.0,
        education_requirements="Cử nhân CNTT hoặc tương đương",
        skills=[
            JDSkill(name="Python", priority=SkillPriority.MUST_HAVE, min_yoe=3.0),
            JDSkill(name="FastAPI", priority=SkillPriority.MUST_HAVE),
            JDSkill(name="PostgreSQL", priority=SkillPriority.MUST_HAVE),
            JDSkill(name="Docker", priority=SkillPriority.MUST_HAVE),
            JDSkill(name="Kubernetes", priority=SkillPriority.MUST_HAVE),
            JDSkill(name="AWS", priority=SkillPriority.NICE_TO_HAVE),
            JDSkill(name="Microservices", priority=SkillPriority.NICE_TO_HAVE),
            JDSkill(name="Redis", priority=SkillPriority.NICE_TO_HAVE),
        ],
        responsibilities=[
            "Thiết kế và phát triển hệ thống backend",
            "Code review và mentoring junior developers",
        ],
    )


@pytest.fixture
def sample_eval_report():
    return EvaluationReport(
        overall_score=78.0,
        recommendation=Recommendation.PASS,
        score_breakdown=[
            CategoryScore(
                category="Must-have Skills", score=85.0, weight=0.4,
                weighted_score=34.0, feedback="Đầy đủ các kỹ năng must-have"
            ),
            CategoryScore(
                category="Nice-to-have Skills", score=80.0, weight=0.15,
                weighted_score=12.0, feedback="Có AWS và Redis"
            ),
            CategoryScore(
                category="Kinh nghiệm", score=70.0, weight=0.25,
                weighted_score=17.5, feedback="Có metrics nhưng một số mục chung chung"
            ),
            CategoryScore(
                category="Học vấn & Chứng chỉ", score=90.0, weight=0.1,
                weighted_score=9.0, feedback="Phù hợp ngành, có chứng chỉ AWS"
            ),
            CategoryScore(
                category="Trình bày CV", score=55.0, weight=0.1,
                weighted_score=5.5, feedback="Thiếu action verbs ở một số mục"
            ),
        ],
        skill_analysis=[
            SkillMatch(
                skill_name="Python", matched=True, cv_evidence="5.5 năm kinh nghiệm",
                is_must_have=True, score=10.0,
            ),
            SkillMatch(
                skill_name="FastAPI", matched=True, cv_evidence="Xây dựng REST API",
                is_must_have=True, score=9.0,
            ),
            SkillMatch(
                skill_name="Go", matched=False,
                is_must_have=False, score=0.0, note="Không có trong CV"
            ),
        ],
        experience_feedback=[
            ExperienceFeedback(
                company="Công ty ABC",
                original_text="Phát triển tính năng mới cho hệ thống",
                issue="Quá chung chung, thiếu metrics",
                has_metrics=False,
                impact_score=3.0,
            ),
        ],
        rewrite_suggestions=[
            RewriteSuggestion(
                original_text="Phát triển tính năng mới cho hệ thống",
                rewritten_text="Xây dựng 5 tính năng mới cho module thanh toán, giúp tăng 15% tỷ lệ chuyển đổi",
                improvement_reason="Thêm số liệu cụ thể và action verb mạnh",
            ),
        ],
        strengths=["Kinh nghiệm solid với Python/FastAPI", "Có chứng chỉ AWS"],
        weaknesses=["Một số mục kinh nghiệm thiếu metrics"],
        final_conclusion="Ứng viên phù hợp tốt với vị trí Senior Backend Developer.",
    )


# ──────────────────────────────────────────────
# Test 1: Output Schemas
# ──────────────────────────────────────────────

class TestOutputSchemas:
    """Test tính hợp lệ của các Pydantic schema."""

    def test_cv_information_valid(self, sample_cv_parsed):
        """CVInformation có thể tạo với dữ liệu đầy đủ."""
        assert sample_cv_parsed.full_name == "Đoàn Quốc Thái"
        assert sample_cv_parsed.total_yoe == 5.5
        assert len(sample_cv_parsed.work_experience) == 2
        assert len(sample_cv_parsed.skills.technical_skills) == 8

    def test_cv_information_minimal(self):
        """CVInformation có thể tạo với dữ liệu tối thiểu (tất cả Optional)."""
        cv = CVInformation()
        assert cv.full_name is None
        assert cv.education is None
        assert cv.work_experience is None

    def test_cv_information_serialization(self, sample_cv_parsed):
        """CVInformation serialize/deserialize đúng."""
        json_str = sample_cv_parsed.model_dump_json()
        restored = CVInformation.model_validate_json(json_str)
        assert restored.full_name == sample_cv_parsed.full_name
        assert restored.total_yoe == sample_cv_parsed.total_yoe

    def test_jd_requirements_valid(self, sample_jd_parsed):
        """JDRequirements có thể tạo với dữ liệu đầy đủ."""
        assert sample_jd_parsed.job_title == "Senior Backend Developer"
        must_haves = [s for s in sample_jd_parsed.skills if s.priority == SkillPriority.MUST_HAVE]
        nice_to_haves = [s for s in sample_jd_parsed.skills if s.priority == SkillPriority.NICE_TO_HAVE]
        assert len(must_haves) == 5
        assert len(nice_to_haves) == 3

    def test_evaluation_report_score_constraint(self):
        """EvaluationReport.overall_score phải nằm trong [0, 100]."""
        with pytest.raises(Exception):
            EvaluationReport(
                overall_score=150.0,  # Vượt quá 100
                recommendation=Recommendation.PASS,
                score_breakdown=[],
                skill_analysis=[],
                experience_feedback=[],
                rewrite_suggestions=[],
                strengths=[],
                weaknesses=[],
                final_conclusion="Test",
            )

    def test_evaluation_report_negative_score(self):
        """EvaluationReport.overall_score không được âm."""
        with pytest.raises(Exception):
            EvaluationReport(
                overall_score=-5.0,
                recommendation=Recommendation.REJECT,
                score_breakdown=[],
                skill_analysis=[],
                experience_feedback=[],
                rewrite_suggestions=[],
                strengths=[],
                weaknesses=[],
                final_conclusion="Test",
            )

    def test_skill_match_score_constraint(self):
        """SkillMatch.score phải nằm trong [0, 10]."""
        valid = SkillMatch(
            skill_name="Python", matched=True, is_must_have=True, score=10.0
        )
        assert valid.score == 10.0

        with pytest.raises(Exception):
            SkillMatch(
                skill_name="Python", matched=True, is_must_have=True, score=15.0
            )

    def test_recommendation_enum(self):
        """Recommendation enum có đúng 3 giá trị."""
        assert Recommendation.PASS.value == "PASS"
        assert Recommendation.CONSIDER.value == "CONSIDER"
        assert Recommendation.REJECT.value == "REJECT"

    def test_skill_priority_enum(self):
        """SkillPriority enum có đúng 2 giá trị."""
        assert SkillPriority.MUST_HAVE.value == "must_have"
        assert SkillPriority.NICE_TO_HAVE.value == "nice_to_have"


# ──────────────────────────────────────────────
# Test 2: validate_report
# ──────────────────────────────────────────────

class TestValidateReport:
    """Test hàm validate_report trong eval.py."""

    def _make_report(self, score: float, recommendation: Recommendation) -> EvaluationReport:
        """Helper tạo EvaluationReport nhanh."""
        return EvaluationReport(
            overall_score=score,
            recommendation=recommendation,
            score_breakdown=[],
            skill_analysis=[],
            experience_feedback=[],
            rewrite_suggestions=[],
            strengths=["test"],
            weaknesses=["test"],
            final_conclusion="Test conclusion",
        )

    def test_pass_correct(self):
        """Score >= 70 + PASS → giữ nguyên."""
        report = self._make_report(85.0, Recommendation.PASS)
        result = validate_report(report)
        assert result.recommendation == Recommendation.PASS

    def test_consider_correct(self):
        """50 <= Score < 70 + CONSIDER → giữ nguyên."""
        report = self._make_report(60.0, Recommendation.CONSIDER)
        result = validate_report(report)
        assert result.recommendation == Recommendation.CONSIDER

    def test_reject_correct(self):
        """Score < 50 + REJECT → giữ nguyên."""
        report = self._make_report(30.0, Recommendation.REJECT)
        result = validate_report(report)
        assert result.recommendation == Recommendation.REJECT

    def test_fix_pass_to_reject(self):
        """Score 30 nhưng LLM trả PASS → sửa thành REJECT."""
        report = self._make_report(30.0, Recommendation.PASS)
        result = validate_report(report)
        assert result.recommendation == Recommendation.REJECT

    def test_fix_reject_to_pass(self):
        """Score 85 nhưng LLM trả REJECT → sửa thành PASS."""
        report = self._make_report(85.0, Recommendation.REJECT)
        result = validate_report(report)
        assert result.recommendation == Recommendation.PASS

    def test_fix_pass_to_consider(self):
        """Score 55 nhưng LLM trả PASS → sửa thành CONSIDER."""
        report = self._make_report(55.0, Recommendation.PASS)
        result = validate_report(report)
        assert result.recommendation == Recommendation.CONSIDER

    def test_boundary_70(self):
        """Score đúng 70 → PASS."""
        report = self._make_report(70.0, Recommendation.CONSIDER)
        result = validate_report(report)
        assert result.recommendation == Recommendation.PASS

    def test_boundary_50(self):
        """Score đúng 50 → CONSIDER."""
        report = self._make_report(50.0, Recommendation.REJECT)
        result = validate_report(report)
        assert result.recommendation == Recommendation.CONSIDER

    def test_boundary_0(self):
        """Score 0 → REJECT."""
        report = self._make_report(0.0, Recommendation.REJECT)
        result = validate_report(report)
        assert result.recommendation == Recommendation.REJECT

    def test_boundary_100(self):
        """Score 100 → PASS."""
        report = self._make_report(100.0, Recommendation.PASS)
        result = validate_report(report)
        assert result.recommendation == Recommendation.PASS


# ──────────────────────────────────────────────
# Test 3: Routing functions (graph.py)
# ──────────────────────────────────────────────

class TestRoutingFunctions:
    """Test các hàm routing trong graph.py."""

    def test_check_readiness_returns_empty(self):
        """check_readiness luôn trả dict rỗng."""
        state = {"cv_parsed": None, "jd_parsed": None, "errors": []}
        result = check_readiness(state)
        assert result == {}

    def test_should_evaluate_success(self, sample_cv_parsed, sample_jd_parsed):
        """Cả 2 parsed + không errors → evaluate."""
        state = {
            "cv_parsed": sample_cv_parsed,
            "jd_parsed": sample_jd_parsed,
            "errors": [],
        }
        assert should_evaluate(state) == "evaluate"

    def test_should_evaluate_with_errors(self, sample_cv_parsed, sample_jd_parsed):
        """Có errors → end."""
        state = {
            "cv_parsed": sample_cv_parsed,
            "jd_parsed": sample_jd_parsed,
            "errors": ["Có lỗi gì đó"],
        }
        assert should_evaluate(state) == "end"

    def test_should_evaluate_missing_cv(self, sample_jd_parsed):
        """Thiếu cv_parsed → end."""
        state = {
            "cv_parsed": None,
            "jd_parsed": sample_jd_parsed,
            "errors": [],
        }
        assert should_evaluate(state) == "end"

    def test_should_evaluate_missing_jd(self, sample_cv_parsed):
        """Thiếu jd_parsed → end."""
        state = {
            "cv_parsed": sample_cv_parsed,
            "jd_parsed": None,
            "errors": [],
        }
        assert should_evaluate(state) == "end"

    def test_should_evaluate_missing_both(self):
        """Thiếu cả 2 → end."""
        state = {"cv_parsed": None, "jd_parsed": None, "errors": []}
        assert should_evaluate(state) == "end"


# ──────────────────────────────────────────────
# Test 4: extractor_node (mock LLM)
# ──────────────────────────────────────────────

class TestExtractorNode:
    """Test node extract_cv với mock LLM."""

    @pytest.mark.asyncio
    async def test_extract_success(self, sample_cv_text, sample_cv_parsed):
        """Extract thành công → trả cv_parsed."""
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke.return_value = sample_cv_parsed

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm

        with patch(
            "src.agents.evaluation_agent.nodes.extract_cv.get_extraction_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.extract_cv._extract_with_retry",
            new=mock_structured_llm.ainvoke,
        ):
            from src.agents.evaluation_agent.nodes.extract_cv import extractor_node

            state = {"cv_content": sample_cv_text, "errors": []}
            result = await extractor_node(state)

            assert "cv_parsed" in result
            assert result["cv_parsed"].full_name == "Đoàn Quốc Thái"

    @pytest.mark.asyncio
    async def test_extract_empty_cv(self):
        """CV rỗng → trả errors."""
        from src.agents.evaluation_agent.nodes.extract_cv import extractor_node

        state = {"cv_content": "", "errors": []}
        result = await extractor_node(state)

        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_extract_none_cv(self):
        """CV None → trả errors."""
        from src.agents.evaluation_agent.nodes.extract_cv import extractor_node

        state = {"cv_content": None, "errors": []}
        result = await extractor_node(state)

        assert "errors" in result
        assert "Không tìm thấy nội dung CV" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_extract_llm_error(self, sample_cv_text):
        """LLM lỗi → trả errors (không crash)."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=Exception("LLM connection timeout")
        )

        with patch(
            "src.agents.evaluation_agent.nodes.extract_cv.get_extraction_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.extract_cv._extract_with_retry",
            side_effect=Exception("LLM connection timeout"),
        ):
            from src.agents.evaluation_agent.nodes.extract_cv import extractor_node

            state = {"cv_content": sample_cv_text, "errors": []}
            result = await extractor_node(state)

            assert "errors" in result
            assert "LLM connection timeout" in result["errors"][0]


# ──────────────────────────────────────────────
# Test 5: parse_jd_node (mock LLM)
# ──────────────────────────────────────────────

class TestParseJDNode:
    """Test node parse_jd với mock LLM."""

    @pytest.mark.asyncio
    async def test_parse_jd_success(self, sample_jd_text, sample_jd_parsed):
        """Parse JD thành công → trả jd_parsed."""
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke.return_value = sample_jd_parsed

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm

        with patch(
            "src.agents.evaluation_agent.nodes.parse_jd.get_extraction_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.parse_jd._parse_jd_with_retry",
            new=mock_structured_llm.ainvoke,
        ):
            from src.agents.evaluation_agent.nodes.parse_jd import parse_jd_node

            state = {"job_requirement": sample_jd_text, "errors": []}
            result = await parse_jd_node(state)

            assert "jd_parsed" in result
            assert result["jd_parsed"].job_title == "Senior Backend Developer"

    @pytest.mark.asyncio
    async def test_parse_jd_empty(self):
        """JD rỗng → trả errors."""
        from src.agents.evaluation_agent.nodes.parse_jd import parse_jd_node

        state = {"job_requirement": "", "errors": []}
        result = await parse_jd_node(state)

        assert "errors" in result

    @pytest.mark.asyncio
    async def test_parse_jd_none(self):
        """JD None → trả errors."""
        from src.agents.evaluation_agent.nodes.parse_jd import parse_jd_node

        state = {"job_requirement": None, "errors": []}
        result = await parse_jd_node(state)

        assert "errors" in result
        assert "Không tìm thấy nội dung JD" in result["errors"][0]


# ──────────────────────────────────────────────
# Test 6: eval_node (mock LLM)
# ──────────────────────────────────────────────

class TestEvalNode:
    """Test node eval với mock LLM."""

    @pytest.mark.asyncio
    async def test_eval_success(self, sample_cv_parsed, sample_jd_parsed, sample_eval_report):
        """Eval thành công → trả eval_report."""
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke.return_value = sample_eval_report

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm

        with patch(
            "src.agents.evaluation_agent.nodes.eval.get_evaluation_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.eval._eval_with_retry",
            new=mock_structured_llm.ainvoke,
        ):
            from src.agents.evaluation_agent.nodes.eval import eval_node

            state = {
                "cv_parsed": sample_cv_parsed,
                "jd_parsed": sample_jd_parsed,
                "errors": [],
            }
            result = await eval_node(state)

            assert "eval_report" in result
            assert result["eval_report"].overall_score == 78.0
            assert result["eval_report"].recommendation == Recommendation.PASS

    @pytest.mark.asyncio
    async def test_eval_missing_cv(self, sample_jd_parsed):
        """Thiếu cv_parsed → trả errors."""
        from src.agents.evaluation_agent.nodes.eval import eval_node

        state = {"cv_parsed": None, "jd_parsed": sample_jd_parsed, "errors": []}
        result = await eval_node(state)

        assert "errors" in result
        assert "Không tìm thấy CV đã phân tích" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_eval_missing_jd(self, sample_cv_parsed):
        """Thiếu jd_parsed → trả errors."""
        from src.agents.evaluation_agent.nodes.eval import eval_node

        state = {"cv_parsed": sample_cv_parsed, "jd_parsed": None, "errors": []}
        result = await eval_node(state)

        assert "errors" in result
        assert "Không tìm thấy JD đã phân tích" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_eval_validates_recommendation(self, sample_cv_parsed, sample_jd_parsed):
        """Eval node tự động sửa recommendation nếu không khớp score."""
        # LLM trả score=30 nhưng recommendation=PASS → phải sửa thành REJECT
        bad_report = EvaluationReport(
            overall_score=30.0,
            recommendation=Recommendation.PASS,  # Sai!
            score_breakdown=[],
            skill_analysis=[],
            experience_feedback=[],
            rewrite_suggestions=[],
            strengths=["test"],
            weaknesses=["test"],
            final_conclusion="Test",
        )

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke.return_value = bad_report

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm

        with patch(
            "src.agents.evaluation_agent.nodes.eval.get_evaluation_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.eval._eval_with_retry",
            new=mock_structured_llm.ainvoke,
        ):
            from src.agents.evaluation_agent.nodes.eval import eval_node

            state = {
                "cv_parsed": sample_cv_parsed,
                "jd_parsed": sample_jd_parsed,
                "errors": [],
            }
            result = await eval_node(state)

            assert result["eval_report"].recommendation == Recommendation.REJECT

    @pytest.mark.asyncio
    async def test_eval_llm_error(self, sample_cv_parsed, sample_jd_parsed):
        """LLM lỗi → trả errors (không crash)."""
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=Exception("Model overloaded")
        )

        with patch(
            "src.agents.evaluation_agent.nodes.eval.get_evaluation_llm",
            return_value=mock_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.eval._eval_with_retry",
            side_effect=Exception("Model overloaded"),
        ):
            from src.agents.evaluation_agent.nodes.eval import eval_node

            state = {
                "cv_parsed": sample_cv_parsed,
                "jd_parsed": sample_jd_parsed,
                "errors": [],
            }
            result = await eval_node(state)

            assert "errors" in result
            assert "Model overloaded" in result["errors"][0]


# ──────────────────────────────────────────────
# Test 7: Integration — Full Graph (mock LLM)
# ──────────────────────────────────────────────

class TestFullGraph:
    """Integration test: chạy full graph với mock LLM."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, sample_cv_text, sample_jd_text,
        sample_cv_parsed, sample_jd_parsed, sample_eval_report,
    ):
        """Full pipeline: CV + JD → EvaluationReport."""
        # Mock extraction LLM (cho extract_cv và parse_jd)
        mock_extract_llm = MagicMock()
        mock_extract_structured_cv = AsyncMock(return_value=sample_cv_parsed)
        mock_extract_structured_jd = AsyncMock(return_value=sample_jd_parsed)

        # Mock evaluation LLM (cho eval)
        mock_eval_llm = MagicMock()
        mock_eval_structured = AsyncMock(return_value=sample_eval_report)

        with patch(
            "src.agents.evaluation_agent.nodes.extract_cv.get_extraction_llm",
            return_value=mock_extract_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.extract_cv._extract_with_retry",
            new=mock_extract_structured_cv,
        ), patch(
            "src.agents.evaluation_agent.nodes.parse_jd.get_extraction_llm",
            return_value=mock_extract_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.parse_jd._parse_jd_with_retry",
            new=mock_extract_structured_jd,
        ), patch(
            "src.agents.evaluation_agent.nodes.eval.get_evaluation_llm",
            return_value=mock_eval_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.eval._eval_with_retry",
            new=mock_eval_structured,
        ):
            from src.agents.evaluation_agent.graph import build_evaluation_graph

            graph = build_evaluation_graph()
            result = await graph.ainvoke({
                "cv_content": sample_cv_text,
                "job_requirement": sample_jd_text,
                "errors": [],
            })

            # Kiểm tra kết quả cuối cùng
            assert result.get("cv_parsed") is not None
            assert result.get("jd_parsed") is not None
            assert result.get("eval_report") is not None
            assert result["eval_report"].overall_score == 78.0
            assert result["eval_report"].recommendation == Recommendation.PASS
            assert not result.get("errors")

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_cv_error(self, sample_jd_text, sample_jd_parsed):
        """CV extract lỗi → pipeline dừng, không chạy evaluate."""
        mock_extract_llm = MagicMock()
        mock_extract_structured_jd = AsyncMock(return_value=sample_jd_parsed)

        with patch(
            "src.agents.evaluation_agent.nodes.extract_cv.get_extraction_llm",
            return_value=mock_extract_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.extract_cv._extract_with_retry",
            side_effect=Exception("CV parse failed"),
        ), patch(
            "src.agents.evaluation_agent.nodes.parse_jd.get_extraction_llm",
            return_value=mock_extract_llm,
        ), patch(
            "src.agents.evaluation_agent.nodes.parse_jd._parse_jd_with_retry",
            new=mock_extract_structured_jd,
        ):
            from src.agents.evaluation_agent.graph import build_evaluation_graph

            graph = build_evaluation_graph()
            result = await graph.ainvoke({
                "cv_content": "some cv text",
                "job_requirement": sample_jd_text,
                "errors": [],
            })

            # Phải có errors
            assert result.get("errors")
            # eval_report không được tạo
            assert result.get("eval_report") is None
